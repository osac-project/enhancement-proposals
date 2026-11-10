# Clarification Log — OSAC-6837

## Status

- Rounds completed: 18
- Open gaps: 0
- Exit criteria met: Yes

## Round 1 — Provider administrator IdP experience

### R1.Q1: Management interfaces

The ticket specifies a UI for configuring provider-administrator sign-in. Do
Cloud Provider Admins also need to manage this configuration through an API or
CLI for automation, or is the UI the only supported management interface?

#### Answer

Cloud Provider Admins must be able to manage IdP configuration through the UI,
API, and CLI.

#### Impact

The PRD must cover configuration management through all three interfaces.

#### Decision (D1)

IdP configuration is supported through the UI, API, and CLI.

---

### R1.Q2: Supported identity providers

Which identity provider products or sign-in standards must Cloud Provider
Admin authentication support for milestone 0.5? If this is not decided yet,
which providers or standards are mandatory for the first release?

#### Answer

OSAC connects to the configured IdP through OIDC. Round 6 clarified the
wording of this requirement.

#### Impact

The PRD must describe the OIDC connection to the configured IdP.

#### Decision (D2)

Superseded by D15 in Round 6. OSAC connects to the configured IdP through
OIDC; the requirement does not name a specific IdP product.

---

### R1.Q3: Sign-in behavior

After an IdP is configured, should it replace the current provider-admin
sign-in, remain an optional sign-in choice, or coexist with more than one
configured IdP? Should another sign-in route remain available?

#### Answer

The configured IdP must coexist with the existing username-and-password
sign-in option.

#### Impact

Provider administrators retain the existing username-and-password option
alongside IdP sign-in.

#### Decision (D3)

IdP sign-in coexists with the existing username-and-password sign-in option.

---

### R1.Q4: Configuration permissions

Should every Cloud Provider Admin be able to view and update IdP settings, or
should configuration changes be limited to a designated subset? Should
viewing and changing settings have different permissions?

#### Answer

Every Cloud Provider Admin can view and change IdP settings. No separate
permissions are needed.

#### Impact

All Cloud Provider Admins have the same access to view and change IdP settings.

#### Decision (D4)

Superseded by D11 in Round 5. Provider IdP management is restricted to the
OSAC break-glass account; ordinary provider roles do not include this
permission.

---

### R1.Q5: Validation and recovery

When an administrator saves IdP settings, what should the product validate
before accepting them (for example, settings format or successful connection
to the IdP)? If a bad update prevents provider administrators from signing in,
what recovery path should they have?

#### Answer

Use the same validation that currently exists for tenant IdPs. If an update
prevents sign-in, administrators can recover by using the admin account shipped
by default with OSAC.

#### Impact

The PRD will require the existing tenant IdP validation behavior and identify
the OSAC-shipped admin account as the recovery sign-in option.

#### Decision (D5)

Superseded by D18 in Round 9: reuse the existing OSAC-1030 System Organization
break-glass account for provider IdP bootstrap and recovery. Round 5 clarifies
validation-before-activation and rollback behavior in D13; Round 11 clarifies
the initial-configuration failure outcome in D20.

---

## Round 2 — IdP authorization

### R2.Q1: Which signed-in identities are Cloud Provider Admins?

The ticket says successful IdP authentication must not itself grant
administrative access. Should a person who signs in through the configured
IdP need to correspond to an identity already authorized as a Cloud Provider
Admin in OSAC, or does this feature need to include a separate enrollment or
approval step for granting Cloud Provider Admin access?

#### Answer

The IdP is registered to the system tenant, which only Cloud Provider
Admin(s) can access. Any user registered to the system tenant is automatically
authorized as a Cloud Provider Admin.

#### Impact

Registration in the system tenant is the authorization boundary: registered
users are Cloud Provider Admins, and the tenant is only accessible to Cloud
Provider Admin(s).

#### Decision (D6)

Superseded by D9 and D10 in Round 5. The internal `system` tenant is not the
provider-user authorization boundary, and registration there does not grant
provider access.

---

## Round 3 — System tenant registration

### R3.Q1: Registering a new Cloud Provider Admin

How does a person become registered to the system tenant: does a Cloud
Provider Admin add them through an existing OSAC tenant-management workflow,
should OSAC register them automatically at first sign-in, or is
another invitation or approval flow required? The ticket says IdP
authentication alone does not grant admin access, so this registration step
sets the authorization boundary.

#### Answer

Use the same just-in-time (JIT) registration as for other tenants. The IdP is
registered to the system tenant, and a user is registered to that tenant on
their first OSAC sign-in.

#### Impact

The system tenant uses the existing tenant JIT registration behavior to add a
user on first OSAC sign-in.

#### Decision (D7)

Superseded by D10 in Round 5. IdP users are JIT-created as OSAC users in
provider scope, not as normal users of the internal `system` tenant.

---

## Round 4 — JIT registration and authorization

### R4.Q1: Does first sign-in grant Cloud Provider Admin access?

The ticket says IdP authentication alone must not grant provider-admin access.
The clarified flow says first OSAC sign-in JIT-registers a user to the system
tenant, and any system-tenant user is automatically authorized as a Cloud
Provider Admin. Does every identity accepted by the configured IdP therefore
become a Cloud Provider Admin on first sign-in, or must a user meet an
existing eligibility or authorization rule before JIT registration? If every
IdP user is intended to become an admin, please confirm that this supersedes
the ticket's requirement that authentication alone does not grant admin
access.

#### Answer

This supersedes the ticket's authorization requirement. If the user comes from
an IdP registered to the system tenant, they are a Cloud Provider Admin.

#### Impact

Any user authenticated through an IdP registered to the system tenant is a
Cloud Provider Admin. This user decision supersedes the ticket's requirement
that authentication alone does not grant admin access.

#### Decision (D8)

Superseded by D9 and D10 in Round 5. IdP authentication establishes identity
only; an explicit provider-scope role assignment grants provider capabilities.

---

## Round 5 — Provider authorization and lifecycle

The following decisions record the user's revision feedback and supersede the
conflicting authorization and configuration decisions above.

### R5.Q1: How does the provider persona relate to authorization?

#### Answer

Cloud Provider Admin describes the provider-user persona and operational
context, not a universal authorization grant. Authentication and JIT user
creation establish identity only. Explicit provider-scope `RoleBinding`
objects grant roles such as full provider administrator
(`cloud-provider-admin`) and provider read-only (`cloud-provider-reader`).
IdP/configuration management is a separate privileged capability reserved
for the break-glass account, not an implied permission of ordinary provider
roles. A `cloud-provider-admin` can assign or remove provider roles.

#### Impact

The PRD must separate the Cloud Provider Admin persona from role-based
capabilities and must not grant provider access to all IdP-authenticated
users.

#### Decision (D9)

Authentication establishes identity only. Provider capabilities require an
explicit provider-scope role assignment. The Cloud Provider Admin persona may
include users with different roles and capabilities.

---

### R5.Q2: How are provider users created and the first role assigned?

#### Answer

IdP users are JIT-created as OSAC users in provider scope, without being
registered as ordinary users of the internal `system` tenant. An authenticated
user without a provider role has no provider-administration access. After the
first external user authenticates and is discoverable as an OSAC user, the
break-glass account creates that user's first provider-scope `RoleBinding`.

#### Impact

The initial external role can be granted after identity discovery without
using `system`-tenant membership as an authorization grant or requiring an
already-authorized external user to bootstrap themselves.

#### Decision (D10)

Provider users are JIT-created in provider scope. The break-glass account
creates the first external provider role binding after the user is discovered;
authentication alone provides no provider access.

---

### R5.Q3: Who can manage the provider IdP?

#### Answer

The OSAC break-glass account configures and recovers the provider IdP and
remains available for recovery. It has limited IdP-management permissions and
can create the first external provider role binding. It is not the day-to-day
provider administrator. Ordinary provider roles do not automatically permit
changes to the authentication boundary.

#### Impact

The PRD must restrict provider IdP configuration to the bootstrap/recovery
path and distinguish IdP management from ordinary provider administration.

#### Decision (D11)

Only the break-glass account manages the provider IdP configuration. Ordinary
provider roles do not grant IdP-management permission. This supersedes D4.
Round 7 clarifies that this feature creates the break-glass account.

---

### R5.Q4: Is role and identity lifecycle behavior part of OSAC-6837?

#### Answer

The role and identity lifecycle behavior is outside OSAC-6837 and will be
addressed by a separate feature.

#### Impact

Those lifecycle semantics are not specified by this PRD.

#### Decision (D12)

Superseded by D17. Role and identity lifecycle behavior is not part of
OSAC-6837 and will be addressed by a separate feature.

---

### R5.Q5: How are IdP configuration updates validated and rolled back?

#### Answer

A new or changed IdP configuration must validate successfully before it is
activated. If validation fails, the previous working configuration remains
active and the user receives actionable feedback.

#### Impact

The PRD must define validation as a condition for activation and preserve the
working configuration after a failed update.

#### Decision (D13)

Validate before activation. A failed update leaves the previous working IdP
configuration active.

This decision's activation wording is superseded by D27. Validation and
preservation of the previous configuration on failed update remain required.

---

### R5.Q6: How are client secrets protected and rotated?

#### Answer

Client secrets are write-only and redacted from API responses, UI and CLI
output, errors, and logs. Omitting a secret during an update preserves the
current value. Supplying a replacement rotates it only after the updated
configuration validates and activates; a failed update leaves the old secret
active.

#### Impact

The PRD must cover secret visibility, update omission, rotation, and failed
rotation behavior across the supported management interfaces.

#### Decision (D14)

Client secrets are write-only and redacted from responses, UI/CLI output,
errors, and logs. Omission preserves the current secret; a supplied
replacement takes effect only with a successfully validated configuration.

---

## Round 6 — OIDC connection wording

### R6.Q1: How should the provider IdP connection be described?

#### Answer

The feature configures OSAC's connection to an IdP through OIDC. The PRD
should describe that connection without naming a specific IdP product.

#### Impact

The PRD should focus on configuring OSAC's OIDC connection to an IdP.

#### Decision (D15)

Configure OSAC's connection to an IdP through OIDC without naming a specific
IdP product. This supersedes D2's earlier provider-specific wording.

---

## Round 7 — Provider break-glass account

### R7.Q1: Does OSAC already have a provider break-glass account?

#### Answer

No. This feature must create a dedicated OSAC break-glass account as part of
the provider IdP capability. The account is limited to provider IdP
configuration, recovery, and assigning the first external provider role. It
is not the day-to-day provider administrator.

#### Impact

The PRD must include creating the account as feature scope and must not imply
that an OSAC-shipped provider break-glass account already exists.

#### Decision (D16)

Create a dedicated provider break-glass account as part of this feature. Limit
it to provider IdP bootstrap and recovery, including the first external
provider-role assignment. Superseded by D18: reuse the existing OSAC-1030
System Organization break-glass account instead of creating a separate one.

---

## Round 8 — Role and identity lifecycle scope

### R8.Q1: Is provider role and identity lifecycle behavior part of OSAC-6837?

#### Answer

No. This behavior will change in a separate feature and should not be
specified in this PRD.

#### Impact

Remove lifecycle behavior from the OSAC-6837 PRD.

#### Decision (D17)

Role and identity lifecycle behavior is outside the scope of OSAC-6837 and
will be addressed by a separate feature. This supersedes D12.

---

## Round 9 — System Organization break-glass account

### R9.Q1: Should OSAC-6837 reuse the System Organization account or create a separate one?

#### Answer

Reuse the existing OSAC-1030 System Organization break-glass account,
`system-osac-break-glass`, in the System Organization's Keycloak realm. It has
the built-in `idp-manager` role and is not a regular JIT-provisioned
system-tenant user. Do not create a separate provider-only account.

The temporary initial password is disclosed once to the authorized Cloud
Provider Admin in the System Organization creation response and confirmation
dialog, and must be changed at first login. If credentials are lost or need
rotation, an authorized Keycloak administrator can reset the password through
the Keycloak Admin Console or API; the account holder changes the temporary
password at the next login. This feature defines no periodic rotation
interval. Round 13 corrects the delivery assumption: the built-in system
tenant is migration-seeded and has no tenant-create response or confirmation
dialog.

#### Impact

The PRD and recovery documentation must identify the account, its realm and
role, initial credential delivery, first-login password change, and reset or
rotation process.

#### Decision (D18)

Provider IdP bootstrap and recovery reuse the OSAC-1030 System Organization
break-glass account in the System Organization's Keycloak realm. No separate
provider-only account is created. First-login change and Keycloak-admin reset
remain applicable. Round 13 replaces the one-time tenant-create response
assumption with the existing tenant break-glass credential Secret flow. This
supersedes D16.

---

## Round 10 — Provider RoleBinding and API authorization

### R10.Q1: How do provider RoleBindings relate to the System Organization and API authorization?

Does provider-scope `RoleBinding` authorization replace the OSAC-1030 System
Organization model? How are assignments represented in Keycloak, and which
authorization path do existing APIs use for provider users?

#### Answer

Keep the OSAC-1030 System Organization identity and role model. JIT-created
provider users are associated with the System Organization identity scope,
not provisioned as ordinary users of the internal `system` tenant. Provider
user `RoleBinding` assignments are authoritative and map one-to-one to
same-named Keycloak realm roles in the System Organization realm. IdP groups
or claims are not an alternate provider-role grant.

Human provider API requests use Fulfillment's existing JWT authorization path:
the shared OPA/Rego policy evaluates role and group claims from the token. The
current policy recognizes `cloud-provider-reader` as a reader, but does not
recognize `cloud-provider-admin` as an admin role. The feature must align the
shared policy with provider roles and require provider API components to use
the same role-to-capability decisions. The managed service-account
RoleBinding resolver is a separate authorization path and does not define
human provider-user access. The existing generic `admins` group rule must not
bypass explicit provider-role assignment for provider-user requests.

#### Impact

The PRD must preserve the System Organization model, define RoleBinding to
Keycloak role mapping, distinguish human-user JWT authorization from managed
service-account authorization, and require consistent provider role
decisions across APIs and components.

#### Decision (D19)

Provider RoleBindings extend the OSAC-1030 System Organization model; they do
not replace it or make the internal `system` tenant a normal user tenant.
User RoleBindings map one-to-one to same-named realm roles. Human provider
API authorization uses the shared OPA/Rego policy over JWT claims; this
feature must make its provider-role interpretation consistent across
components, including recognizing `cloud-provider-admin` as a provider
administrator. The generic `admins` group rule must not bypass provider-role
assignment. IdP authentication, group membership alone, and internal
`system`-tenant registration do not grant provider access.

---

## Round 11 — Initial IdP validation failure

### R11.Q1: What happens when the first provider IdP configuration fails validation?

Should failed validation of an initial configuration leave an IdP active, and
how can an administrator retry? How should this differ from a failed update
when a working configuration already exists?

#### Answer

Leave the initial provider IdP inactive if validation fails. Keep
`system-osac-break-glass` usable so the configuration can be corrected and
retried. For a failed update, keep the previous working configuration active.
Return actionable feedback for either failure.

#### Impact

The PRD must distinguish initial configuration failure from update rollback
and preserve the break-glass recovery path while no provider IdP is active.

#### Decision (D20)

Initial validation failure leaves the provider IdP inactive and the
`system-osac-break-glass` account usable to correct and retry configuration.
Update validation failure preserves the previous working configuration.
Both cases return actionable feedback. This refines D13.

The initial-failure outcome in this decision is superseded by D27. A failed
initial configuration is not saved or applied; a failed update preserves the
previous current configuration.

---

## Round 12 — Provider sign-in methods

### R12.Q1: Which provider users may use local username-and-password sign-in?

Should local username-and-password sign-in remain available to every provider
user alongside the configured OIDC IdP, or be limited to the recovery account?

#### Answer

Limit local username-and-password authentication to
`system-osac-break-glass` for provider IdP bootstrap and recovery. Regular
provider users continue to sign in through the configured OIDC IdP.

#### Impact

The PRD must distinguish the break-glass recovery sign-in from regular
provider-user sign-in.

#### Decision (D21)

Local username-and-password sign-in is available only to
`system-osac-break-glass`. Regular provider users authenticate through the
configured OIDC IdP. This narrows D3's coexistence requirement for the
provider flow.

---

## Round 13 — System break-glass credential Secret

### R13.Q1: How does an operator obtain the automatically created system break-glass credential?

Can OSAC reuse the tenant break-glass credential Secret flow for the built-in
system account, given that no user creates the system tenant through the UI
or API?

#### Answer

Reuse the tenant break-glass credential Secret flow. During system bootstrap,
store the temporary `system-osac-break-glass` username and password in a
Secret scoped to the internal `system` tenant. An authorized platform
administrator or controller can retrieve it through the existing Secrets
Get authorization path. Do not claim the credential is delivered in a
tenant-create response or confirmation dialog. The account holder changes
the temporary password at first login. An authorized Keycloak administrator
handles later password resets or rotation through the Keycloak Admin Console
or API.

The current system tenant is seeded by a database migration, and its current
reconciliation path does not persist the password generated during account
creation. The feature must connect that generated credential to the existing
Secret persistence path before it can be retrieved.

#### Impact

The PRD must use the existing tenant credential Secret flow, state that
system-scoped Secret retrieval is restricted to platform administrators and
controllers, and avoid describing a tenant-create response for the built-in
system tenant.

#### Decision (D22)

The system break-glass account reuses the tenant break-glass credential
Secret flow. Its initial credential is stored in a system-scoped Secret and
retrieved only through existing platform-secret authorization. The system
bootstrap implementation must persist the generated password before the
reconciler discards it. D22 supersedes D18's one-time tenant-create response
and confirmation-dialog assumption; account reuse, realm/scope, and
Keycloak-admin reset remain as decided in D18.

---

## Round 14 — Remove auditing role

### R14.Q1: Should auditing remain a provider role or capability in this PRD?

#### Answer

Remove auditing from the provider roles and capabilities specified by this
PRD.

#### Impact

The PRD must no longer list auditing as a provider role or capability.

#### Decision (D23)

Auditing is removed from the provider role and capability scope of OSAC-6837.

---

## Round 15 — Break-glass role name

### R15.Q1: Which role is assigned to the break-glass account in the current implementation?

#### Answer

The tenant creation flow assigns the `tenant-idp-manager` Keycloak realm
role directly to the break-glass user.

#### Impact

The PRD must use the role name assigned by the current implementation.

#### Decision (D24)

Use `tenant-idp-manager` for the break-glass role name. This supersedes the
`idp-manager` wording in D18 and its earlier answer.

---

## Round 16 — System break-glass removal and recovery

### R16.Q1: What happens if the system break-glass user is removed from Keycloak?

Does disabling or deleting the Keycloak account, or removing it from the
System Organization, revoke system-tenant membership and block local sign-in?
How must OSAC re-evaluate access, and how can the account be recovered?

#### Answer

Disabling or deleting `system-osac-break-glass` in Keycloak, or removing it
from the System Organization, revokes its system-tenant identity membership
and `tenant-idp-manager` grant, and blocks local provider sign-in. Removing
organization membership alone must also disable or delete the account so
username-and-password authentication cannot bypass provider recovery. On
each fresh sign-in or token refresh, re-evaluate that the account is enabled,
belongs to the System Organization, and has the `tenant-idp-manager` role.
Deny access if any check fails. Do not JIT-provision or restore membership
automatically. Previously issued access tokens follow the separate
identity-lifecycle behavior.

An authorized platform administrator uses Keycloak administrative access and
the existing OSAC-1030 bootstrap/recovery path to recreate or re-enable the
account and restore its System Organization membership and `tenant-idp-manager`
role. The administrator rotates its credential through the system-scoped
break-glass Secret flow. Require a fresh sign-in after recovery; the removed
account cannot recover itself.

#### Impact

The PRD must define explicit deprovisioning, fresh-token re-evaluation, and
authorized recovery for the system break-glass account. This is a narrow
exception to the separate feature's general user and token lifecycle scope.

#### Decision (D25)

Disabling or deleting `system-osac-break-glass` in Keycloak, or removing it
from the System Organization, revokes system-tenant identity membership and
the `tenant-idp-manager` grant, and blocks local sign-in. Removing
organization membership alone must disable or delete the account. Fresh
authentication and token refresh fail unless the account is enabled, has
current membership, and has `tenant-idp-manager`; no JIT restoration is
allowed. An authorized platform administrator uses Keycloak administrative
access and the existing OSAC-1030 recovery path to restore the account,
membership, role, and rotated Secret credential, after which a fresh sign-in
is required. Previously issued token handling remains in the separate
lifecycle feature.

This decision is superseded by D26: OSAC-6837 does not add the login,
membership-re-evaluation, or deprovisioning behavior described here.

---

## Round 17 — Scope of break-glass membership re-evaluation

### R17.Q1: Does OSAC-6837 enforce break-glass membership at login or refresh?

Should this feature add OSAC-side checks for the break-glass account's enabled
state, System Organization membership, and `tenant-idp-manager` role whenever
a user signs in or refreshes a token?

#### Answer

No. OSAC-6837 configures OSAC's OIDC connection and uses the existing
break-glass account and sign-in behavior. It does not add a post-token login
check, change Keycloak authentication flows, re-evaluate membership or roles
on refresh, or define deprovisioning and recovery after the account is removed
or disabled. Those authentication and identity-lifecycle changes belong in a
separate feature. This decision does not assert whether existing Keycloak
behavior blocks a particular login or refresh case.

#### Impact

Remove the new system break-glass login, refresh, deprovisioning, and recovery
requirements from OSAC-6837. Track them with the separate identity-lifecycle
feature.

#### Decision (D26)

OSAC-6837 does not add OSAC-side account-status or membership checks during
sign-in or token refresh, nor define break-glass deprovisioning or recovery.
This work belongs to a separate identity-lifecycle feature and supersedes D25.

---

## Round 18 — Provider IdP activation lifecycle

### R18.Q1: Does OSAC-6837 require a separate IdP activation step?

Should a newly created or updated provider IdP configuration require a
separate activation action, or include an enable/disable lifecycle?

#### Answer

No. A newly created or updated configuration must pass validation before it
is accepted and saved as the current provider IdP configuration. No separate
activation action is part of OSAC-6837. If initial validation fails, do not
save or apply the configuration; keep the break-glass account available to
correct and retry. If update validation fails, preserve the previous current
configuration and return actionable feedback. Enabling or disabling an
already configured provider IdP belongs to a separate feature.

#### Impact

Remove the separate activation step and enable/disable lifecycle from the
PRD. Preserve validation-before-save, initial failure behavior, update
rollback, and actionable feedback.

#### Decision (D27)

OSAC-6837 validates each new or changed provider IdP configuration before
accepting it. A valid configuration becomes current when saved; no separate
activation step is required. A failed initial configuration is not saved or
applied. A failed update preserves the previous current configuration. The
feature does not add an enable/disable lifecycle. This supersedes the
activation wording in D13, the initial-failure outcome in D20, and the
activation-dependent secret rotation wording in D14. Validation,
rollback, and client-secret handling remain in scope.

---

## Remaining Gaps

None for OSAC-6837. The provider authorization boundary, bootstrap role
assignment, mapping to the System Organization role model, API authorization
path, IdP configuration permissions, initial validation failure and update
rollback behavior, and secret handling are resolved. Provider-user and
break-glass authentication lifecycle behavior, including sign-in/refresh
membership re-evaluation and recovery after account removal, is assigned to a
separate feature. Enable/disable lifecycle management for the provider IdP is
assigned to a separate feature.
