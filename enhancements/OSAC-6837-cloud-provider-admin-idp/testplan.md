# Testplan — OSAC-6837

## Overview

- **Feature:** OSAC-6837 — Configure an IdP for Cloud Provider Admins
- **Total test cases:** 19
- **Behavioral PRD scope anchors covered:** 7 of 7
- **Documentation-only scope anchors:** 1
- **Interface changes covered:** 5 of 5

A provider user is in the Cloud Provider Admin persona, even before an
explicit provider-role assignment grants the `cloud-provider-admin` capability.
The PRD has no FR/NFR identifiers. `IS1` through `IS8` below refer to the
numbered order of its eight In Scope bullets for test traceability; they do not
add requirement IDs to the PRD. Test-case metadata includes the required tier
and owner. Test-case IDs use the `IS` anchor and a sequence number.

## Test Case Index

| ID | Scenario | IC | Tier | Owner | Priority |
|----|----------|----|------|-------|----------|
| TC-IS1-01 | Create and access multiple provider IdPs | IC-1 | Component integration | [DEV] Fulfillment | high |
| TC-IS1-02 | Provider configuration UI supports multiple IdPs | IC-2 | Unit | [DEV] UI | medium |
| TC-IS1-03 | Delete provider IdP and retain users and role assignments | IC-1 | Component integration | [DEV] Fulfillment | high |
| TC-IS2-01 | Existing invalid-field validation remains active for provider configuration | IC-1 | Component integration | [DEV] Fulfillment | high |
| TC-IS2-02 | Reject malformed update without persisting candidate | IC-1 | Component integration | [DEV] Fulfillment | critical |
| TC-IS2-03 | Save a valid replacement and authenticate through the provider IdP | IC-1 | Component integration | [DEV] Fulfillment | high |
| TC-IS3-01 | Assign, update, and remove provider roles | IC-4 | Component integration | [DEV] Fulfillment | high |
| TC-IS3-02 | Deny provider privileges without a provider-role assignment, including admins-group bypass | IC-4 | Component integration | [DEV] Fulfillment | critical |
| TC-IS3-03 | Verify initial provider admin and break-glass role management | IC-4 | Component integration | [DEV] Fulfillment | high |
| TC-IS4-01 | JIT-create provider User in system without assigning a provider role | IC-3 | Component integration | [DEV] Fulfillment | high |
| TC-IS5-01 | Persist and retrieve break-glass credentials through system Secret access | IC-5 | Component integration | [DEV] Fulfillment | high |
| TC-IS5-02 | Recover break-glass credentials after interrupted bootstrap or reset | IC-5 | Unit | [DEV] Fulfillment | high |
| TC-IS6-01 | Redact client Secret from API and CLI output | IC-1 | Component integration | [DEV] Fulfillment | high |
| TC-IS6-02 | Preserve the existing Secret reference when unchanged | IC-2 | Unit | [DEV] UI | high |
| TC-IS6-03 | Preserve the API Secret reference when omitted | IC-1 | Component integration | [DEV] Fulfillment | high |
| TC-IS7-01 | Authenticate regular provider users through OIDC and break-glass locally | IC-3 | Component integration | [DEV] Fulfillment | critical |
| TC-IS7-02 | Deployed provider sign-in and role journey | IC-3 | E2E | Story 1.07 (QE) | critical |

## Test Cases

### PRD In Scope 1: Configure provider IdPs through UI, API, and CLI

#### TC-IS1-01: Create and access multiple provider IdPs

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-1 | Component integration | [DEV] Fulfillment | high | automated |

##### Preconditions

- The deployed Fulfillment integration environment has Keycloak and PostgreSQL.
- The test has `system-osac-break-glass` and the pre-existing provider user
  with `cloud-provider-admin`.
- The test fixture provisions two system value Secrets and records their
  references before creating provider IdPs.

##### Steps

1. As `system-osac-break-glass`, create one provider IdP using the first
   system Secret reference.
2. As `system-osac-break-glass`, create a second IdP with a distinct name,
   client ID, issuer, and reference to a different preexisting system value
   Secret.
3. Get both IdPs and List the provider IdPs as `system-osac-break-glass`.
4. Update one IdP as `system-osac-break-glass` and verify the other IdP's
   configuration and Secret reference are unchanged.
5. As the pre-existing `cloud-provider-admin` user, attempt to create or update
   a provider IdP.

##### Expected Results

- Both resources have `metadata.tenant` equal to `system` and distinct names.
- Get and List return both resources to `system-osac-break-glass`.
- The pre-existing `cloud-provider-admin` user cannot configure provider IdPs
  solely by holding that provider role.
- The unauthorized create or update returns `PERMISSION_DENIED`.
- Keycloak reconciles each resource to a distinct broker alias.
- Updating one IdP changes only that resource and its Secret reference.

#### TC-IS1-02: Provider configuration UI supports multiple IdPs

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-2 | Unit | [DEV] UI | medium | automated |

**Steps:** 1. Render the provider configuration route with the
  `system-osac-break-glass` identity and two mocked IdP resources → 2. Render
  it with the pre-existing `cloud-provider-admin` identity.
**Expected:** The break-glass view lists the IdPs and exposes controls to add
or update a configuration using a known Secret reference without displaying
its data. The pre-existing provider-admin view does not expose provider IdP
configuration controls.

#### TC-IS1-03: Delete provider IdP and retain users and role assignments

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-1 | Component integration | [DEV] Fulfillment | high | automated |

##### Steps

1. Create a provider IdP, authenticate a provider user, and record its OSAC
   User and an unexpired OSAC access token.
2. As `system-osac-break-glass`, assign `cloud-provider-reader` to that User
   through the supported OSAC role-management workflow. Wait for the
   RoleBinding to reach `READY`, then record its ID and verify the User is
   listed in the binding.
3. Configure the test proxy to return one transient `500` for the Keycloak
   broker-delete request while forwarding the request to Keycloak on retry.
4. As `system-osac-break-glass`, delete the provider IdP through the API.
5. After the first failed delete, verify the IdentityProvider still has its
   controller finalizer and the broker is still present in Keycloak.
6. Allow the controller retry to reach Keycloak; wait for the broker to be
   removed and the IdentityProvider to be finalized, then attempt a new
   sign-in through that IdP.
7. Use the previously issued unexpired token to read the OSAC User, then read
   the recorded RoleBinding by ID.

##### Expected Results

- The IdentityProvider is finalized only after the Keycloak broker is absent.
- The injected transient failure leaves the controller finalizer and Keycloak
  broker in place; the retry removes the broker before finalization.
- New sign-ins through the deleted broker fail; the prior token follows its
  normal expiration and revocation policy.
- The Keycloak account, OSAC User, and RoleBinding remain; deletion does not
  deprovision the user or revoke its role assignment.
- The RoleBinding retains its recorded ID and still lists the provider User
  after IdP deletion.

### PRD In Scope 2: Preserve existing provider-field validation behavior and return actionable errors

The IdentityProvider UI and API already validate required fields, URL syntax,
and Secret references. These cases retain coverage of existing behavior and
verify D27's failed-update preservation requirement; they do not add field
validation work to this design.

#### TC-IS2-01: Existing invalid-field validation remains active for provider configuration

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-1 | Component integration | [DEV] Fulfillment | high | automated |

##### Steps

Run these three candidate rows independently:

1. Submit an initial candidate with a missing required field.
2. Submit an initial candidate with a malformed URL.
3. Submit an initial candidate with an invalid Secret reference or type.
4. For each rejected candidate, correct the field/reference and retry.

##### Expected Results

- The failed initial submission returns a sanitized validation error, and the
  named candidate is absent from Get and List.
- Existing validation checks required fields, URL syntax, and Secret
  reference/type. It makes no outbound request to the external IdP.
- The corrected candidate is saved and retrievable through the provider
  IdentityProviders API.
- The three parameterized candidate rows count as three test cases.

#### TC-IS2-02: Reject malformed update without persisting candidate

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-1 | Component integration | [DEV] Fulfillment | critical | automated |

##### Steps

1. Create a valid provider IdentityProvider configuration.
2. Submit an update with a malformed URL and a replacement
   `client_secret_secret` reference.
3. Get the provider IdentityProvider and inspect the stored Secret reference.

##### Expected Results

- Update returns `INVALID_ARGUMENT` with a sanitized field-level error and
  exposes neither Secret value.
- The malformed candidate and replacement Secret reference are not persisted;
  Get still returns the previously saved configuration and Secret reference.

#### TC-IS2-03: Save a valid replacement and authenticate through the provider IdP

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-1 | Component integration | [DEV] Fulfillment | high | automated |

##### Steps

1. Submit a valid updated configuration with a reference to a replacement
   system value Secret.
2. Authenticate through the replacement test IdP after the valid update is
   accepted.

##### Expected Results

- The updated public configuration is current.
- Authentication succeeds using the replacement client Secret.
- A response or CLI output contains no client-secret bytes.

### PRD In Scope 3: Grant provider capabilities through explicit provider-role assignments

#### TC-IS3-01: Assign, update, and remove provider roles

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-4 | Component integration | [DEV] Fulfillment | high | automated |

##### Steps

1. As `system-osac-break-glass`, use the supported OSAC role-management
   workflow to assign `cloud-provider-admin` and `cloud-provider-reader` to
   separate Users in the `system` tenant.
2. Update the admin assignment to include another system User.
3. Select an existing OSAC User whose `metadata.tenant` is not `system`. As
   `system-osac-break-glass`, assign `cloud-provider-reader` through the
   supported role-management workflow. Verify the assignment succeeds and the
   User's tenant remains unchanged.
4. Authenticate the additional system User through a configured provider IdP
   and call a provider-admin API method.
5. Authenticate as the User from another tenant through that User's existing
   supported login path and call a provider-reader API method. Confirm that
   role assignment has not added `system` tenant access.
6. Remove each assignment after its effect on authorization has been verified.

##### Expected Results

- Provider users receive only the capabilities of their assigned provider
  roles.
- The additional user assigned `cloud-provider-admin` can sign in through a
  configured IdP and use provider-administration capabilities.
- A provider role can be assigned to a User outside the `system` tenant; the
  assignment grants the role's provider capabilities and leaves the User's
  tenant membership unchanged.
- Updating and removing assignments changes the effective authorization.
- After removal, the associated provider capability is denied.

#### TC-IS3-02: Deny provider privileges without a provider-role assignment, including admins-group bypass

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-4 | Component integration | [DEV] Fulfillment | critical | automated |

##### Steps

1. Authenticate a system-tenant provider User with no provider-role assignment
   and call a provider-admin API method.
2. Repeat with the global `admins` group present in the authenticated context.
3. Repeat with external identity group or claim values that resemble
   `cloud-provider-admin`, without a corresponding OSAC role assignment, and
   call a provider-admin API method.
4. Authenticate a roleless provider User with external group or claim values
   that resemble `cloud-provider-reader` and call a provider read API method.

##### Expected Results

- The user's tenant claim remains `system`, but both provider-admin and
  provider-reader operations return `PERMISSION_DENIED` without their
  corresponding OSAC role assignments.
- Neither system-tenant membership nor the global `admins` group grants
  provider-admin capability without an explicit provider-role assignment.
- External identity group or claim membership does not grant either
  provider-admin or provider-reader capability without an explicit
  provider-role assignment.

#### TC-IS3-03: Verify initial provider admin and break-glass role assignment

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-4 | Component integration | [DEV] Fulfillment | high | automated |

##### Preconditions

- The pre-existing provider User already has the `cloud-provider-admin`
  assignment required by the initial-user setup.

##### Steps

1. Authenticate through the provider IdP as the pre-existing user and verify
   its provider-admin capability and `system` tenant access.
2. As `system-osac-break-glass`, assign `cloud-provider-reader` to another
   user after bootstrap. After the role-management workflow completes,
   authenticate as that reader and call a provider read operation.
3. As `system-osac-break-glass`, remove the assignment. After the change takes
   effect, authenticate again as the same user and repeat the provider read.

##### Expected Results

- The pre-existing provider user retains its provider-admin capability and
  system tenant access after authentication.
- Break-glass can grant and remove provider roles after bootstrap. The
  `cloud-provider-reader` user's read operation is authorized after the grant
  and returns `PERMISSION_DENIED` after the removal.

### PRD In Scope 4: JIT-create provider identities with system-tenant access but no implicit role

#### TC-IS4-01: JIT-create provider User in system without assigning a provider role

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-3 | Component integration | [DEV] Fulfillment | high | automated |

##### Steps

1. Authenticate a new user through the configured test IdP.
2. Before assigning the discovered User a provider role through the supported
   OSAC role-management workflow, call a provider-admin API as that user.

##### Expected Results

- The JIT-created User can receive a provider role after first authentication.
- The user has the system tenant claim and baseline client access, but no
  cloud-provider-admin or cloud-provider-reader capability before assignment.
- The provider-admin API returns `PERMISSION_DENIED` before assignment.

### PRD In Scope 5: Persist and retrieve the system break-glass credential through the Secret path

#### TC-IS5-01: Persist and retrieve break-glass credentials through system Secret access

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-5 | Component integration | [DEV] Fulfillment | high | automated |

##### Steps

1. Start system bootstrap and pause the Keycloak password request after the
   `PENDING` operation and credential are durably stored. Verify the new
   account is absent or disabled.
2. From a second authorized operation runner, start a password reset while
   bootstrap is active. Verify it cannot replace the active Secret operation
   or issue a Keycloak password request.
3. Release the bootstrap request and wait for `COMPLETE`. Verify an authorized
   platform administrator can retrieve its credential, then start the reset
   again. Verify the reset receives a new operation ID/owner number and its
   Keycloak write begins only after bootstrap completes.
4. Wait for the reset to complete. Attempt credential retrieval as a regular
   provider user, then sign in as break-glass and change the temporary
   password.
5. Restart the bootstrap/controller after the completed reset and verify the
   account still accepts the user-changed password.

##### Expected Results

- Authorized retrieval returns the generated username and password from a
  Secret in the `system` tenant.
- The concurrent reset cannot replace the active bootstrap credential or
  reach Keycloak until bootstrap completes; the subsequent reset uses a new
  operation ID/owner number.
- The regular provider user's Secret Get returns `PERMISSION_DENIED`.
- The break-glass account can authenticate with the temporary credential and
  Keycloak requires a password change before completing first login.
- The account is not enabled for local sign-in until the Secret and account
  password contain the same credential.
- Restart after the operation reaches `COMPLETE` does not reapply the stored
  temporary password; the user's changed password remains valid.
- No tenant-create response or log contains the credential.

#### TC-IS5-02: Recover break-glass credentials after interrupted bootstrap or reset

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-5 | Unit | [DEV] Fulfillment | high | automated |

##### Steps

1. Start bootstrap operation A, persist its `PENDING` phase and owner
   number, and pause before the Keycloak password write. Start reset
   operation B concurrently.
2. Verify B cannot replace A's credential or issue a Keycloak write while A
   owns the operation. Simulate A's worker stopping; do not transfer
   ownership until it can no longer issue Keycloak writes and its request has
   finished.
3. Have recovery claim and resume A with the same operation ID and credential.
   Attempt a Keycloak write from A's old worker and verify it is rejected
   before reaching Keycloak. Complete A through
   `CREDENTIAL_APPLIED` and `COMPLETE`.
4. Start B after A completes. Verify B receives a newer owner number, then
   interrupt it at `PENDING` and restart recovery.
5. Simulate a stop after `CREDENTIAL_APPLIED` is durable but before the
   account is enabled and `COMPLETE` is persisted; verify recovery resumes
   without reapplying the password.
6. After reset B completes, change the account password at login, restart,
   and verify the changed password remains valid and the stored temporary
   password is not reapplied.
7. Simulate an existing account without a Secret and run bootstrap recovery.
   Verify local sign-in is disabled while a replacement operation is
   persisted and applied.

##### Expected Results

- A `PENDING` operation retries the same stored credential; a
  `CREDENTIAL_APPLIED` operation resumes enablement and completion without
  reapplying it.
- Only the current owner can update the Secret or issue a Keycloak password
  write. Recovery resumes the same operation, and an old worker cannot write
  after ownership transfers.
- Bootstrap and reset use distinct operation IDs. A `COMPLETE` operation is
  not replayed after the account holder changes the password; restart leaves
  the changed password valid.
- Recovery disables local sign-in, persists a replacement credential, applies
  that value to the account, then enables local sign-in.
- Secret persistence or Keycloak failures leave the operation incomplete and
  a new account absent or an existing account disabled until the Secret and
  account credential are consistent.

### PRD In Scope 6: Redact client secrets and preserve an omitted value

#### TC-IS6-01: Redact client Secret from API and CLI output

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-1 | Component integration | [DEV] Fulfillment | high | automated |

##### Steps

1. Create a preprovisioned system Secret whose value contains a unique test
   marker.
2. Create a provider IdP referencing that Secret and inspect the Create
   response.
3. Update a nonsensitive field on that IdP without changing the Secret
   reference and inspect the Update response.
4. Inspect IdentityProviders Get and List results and provider IdP CLI
   Create, Update, Get, and List output for the unique marker.

##### Expected Results

- Create and Update responses, Get and List results, and CLI output contain
  the Secret reference only; none contains the unique Secret value.

#### TC-IS6-02: Preserve the existing Secret reference when unchanged

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-2 | Unit | [DEV] UI | high | automated |

**Steps:** 1. Load an existing provider IdP in the UI → 2. save a valid change
  without changing its Secret reference.
**Expected:** The update request omits `client_secret_secret`; authentication
continues with the Secret already referenced by the IdentityProvider. The UI
does not display the Secret bytes.

#### TC-IS6-03: Preserve the API Secret reference when omitted

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-1 | Component integration | [DEV] Fulfillment | high | automated |

##### Steps

1. Create a provider IdP with a reference to a preprovisioned system Secret.
2. Update another valid configuration field while omitting
   `client_secret_secret` from the request.
3. Get the IdentityProvider and authenticate through its configured test IdP.

##### Expected Results

- Get returns the original Secret reference after the update.
- Authentication succeeds using the Secret already referenced by the
  IdentityProvider.
- API and CLI output contain the reference only, never Secret bytes.

### PRD In Scope 7: Use OIDC for regular provider sign-in and local sign-in only for break-glass

#### TC-IS7-01: Authenticate regular provider users through OIDC and break-glass locally

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-3 | Component integration | [DEV] Fulfillment | critical | automated |

##### Steps

1. Complete the authorization-code flow through each of two configured test
   IdPs as regular provider Users.
2. Attempt local sign-in as `system-osac-break-glass` with a known-valid
   credential.

##### Expected Results

- Each regular provider User receives a valid OSAC token with the `system`
  tenant claim.
- Local sign-in succeeds for break-glass with its known-valid credential.

#### TC-IS7-02: Deployed provider sign-in and role journey

| Interface Change | Tier | Owner | Priority | Automation |
|-----------------|------|-------|----------|------------|
| IC-3 | E2E | Story 1.07 (QE) | critical | proposed |

##### Steps

1. Sign in through the deployed provider OIDC flow as a roleless provider User.
2. Verify system-tenant access and denied provider-admin operations, then
   have `system-osac-break-glass` assign the user `cloud-provider-admin`
   through the supported workflow and repeat the privileged request after the
   assignment takes effect.

##### Expected Results

- The roleless user completes sign-in, receives baseline system-tenant access,
  and receives `PERMISSION_DENIED` for the provider-admin operation.
- After the role assignment takes effect, the same operation is authorized
  according to the assigned provider role.

## Gaps

### Requirement Coverage Gaps

- PRD In Scope 8 (user-facing configuration and sign-in documentation) is
  documentation-only and has no behavioral test case. Review the provider
  setup, sign-in, and credential recovery guide against D21-D22 and the final
  authorization behavior.

### Interface Change Coverage Gaps

- All five Interface Changes have at least one planned test case.

## Test Coverage Matrix

| Component / behavior | PRD / IC | Tier and boundary | Case(s) and suite | Execution, prerequisites, real vs. simulated | Owner / status |
|----------------------|----------|-------------------|-------------------|---------------------------------------------|----------------|
| Existing Fulfillment field validation, multi-IdP API, system-tenant access, deletion, and Secret handling | IS1, IS2, IS6 / IC-1 | Component integration: deployed Fulfillment API, PostgreSQL persistence, and Keycloak IdP reconciliation | TC-IS1-01, TC-IS1-03, TC-IS2-01..03, TC-IS6-01, TC-IS6-03; extend `fulfillment-service/it/it_identity_providers_test.go` | From repo root: `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`. Requires disposable Kind. Fulfillment, PostgreSQL, and Keycloak run for real; the external provider is a temporary test Keycloak realm. A test proxy injects one transient Keycloak delete failure and forwards the retry to real Keycloak. OSAC-6837 validation cases make no outbound requests to the external provider. No operator or AAP workload is involved. | [DEV] Fulfillment; runnable suite exists, system-tenant IdP cases are proposed. |
| OIDC broker login, JIT provisioning, and provider authorization | IS3, IS4, IS7 / IC-3, IC-4 | Component integration: real OIDC sign-in and Fulfillment authorization using the OSAC role-management workflow | TC-IS3-01..03, TC-IS4-01, TC-IS7-01; extend Fulfillment OIDC and authorization integration coverage | Same root command as above. Fulfillment, PostgreSQL, and Keycloak run for real for OIDC sign-in and JIT provisioning; provider-role assignment for Users in both system and other tenants is exercised through the platform role-management boundary. `CreateExtRealm` supplies a temporary Keycloak test realm, not an external commercial IdP. | [DEV] Fulfillment; test setup must align with OSAC-3058. |
| Break-glass bootstrap/reset recovery | IS5 / IC-5 | Unit: in-process Fulfillment bootstrap/controller logic | TC-IS5-02; extend bootstrap/controller suites | From `fulfillment-service/`: `ginkgo run --timeout 20m -r internal` and `ginkgo run --timeout 10m internal/servers`. Mocked operations verify owner numbers, reject writes from old workers, and recover the same operation; this does not prove the deployed Secret/Keycloak boundary. | [DEV] Fulfillment; command and suites are documented in `fulfillment-service/AGENTS.md`. |
| Provider configuration UI and Secret-reference behavior | IS1, IS6 / IC-2 | Unit: React UI rendered with mocked Connect transport | TC-IS1-02, TC-IS6-02; add tests beside the provider configuration page | From `osac-ui/`: `pnpm --filter @osac/app-frontend run test`. UI components run in Vitest; Connect responses are mocked with `createMockConnectTransport`; no live Fulfillment or Keycloak. | [DEV] UI; test command and harness exist. |
| System break-glass credential persistence and access | IS5 / IC-5 | Component integration: bootstrap, Secret authorization, and Keycloak credential writes | TC-IS5-01; extend Fulfillment integration suite after the system bootstrap fixture is available | Same root Fulfillment command. Fulfillment, PostgreSQL, and Keycloak are real. A test proxy pauses and forwards the Keycloak password write while a concurrent reset attempts to claim ownership. The current system bootstrap fixture does not cover this behavior. | [DEV] Fulfillment; proposed case, no current system-bootstrap test. |
| Full deployed provider sign-in and role journey | IS7 / IC-3, IC-4 | E2E: deployed OSAC identity-to-authorization user journey | TC-IS7-02; proposed `tests/e2e/regression/test_provider_admin_idp.py` | No runnable command is defined: the E2E suite has no provider OIDC fixture or broker-login helper. Existing `test_tenant_onboarding.py` uses placeholder OIDC configuration and does not prove broker login. Add a real test IdP fixture and use deployed Keycloak, Fulfillment, PostgreSQL, and public API; no AAP/operator required. | Story 1.07 (QE); execution readiness unresolved until the fixture and story are implemented. |

The manual `osac-ui/apps/playwright` harness can confirm a UI flow against a
live deployment, but it uses throwaway scratch specs and is not persisted CI
coverage. It does not close the E2E automation gap above.

## Graduation Criteria

The feature is ready to graduate when all of the following measurable
conditions are met:

- All 19 planned cases pass, including provider IdP Create, Get,
  List, Update, and Delete behavior and the existing tenant-IdP regression
  cases.
- All three Secret-handling cases pass: API/CLI redaction, UI omission
  behavior, and API reference preservation with successful authentication.
- The provider OIDC E2E case passes against deployed Keycloak, Fulfillment,
  PostgreSQL, and the public API; its fixture and runnable command are
  documented.
- The roleless-to-admin journey passes with `system` tenant access separate
  from provider-role authorization, and external identity attributes do not
  grant provider capabilities.
- The UI unit suite passes, and no critical or high-priority test failure
  remains open.
- Break-glass bootstrap/recovery prove the Secret is durable before local
  sign-in is enabled, credential operations remain serialized through Keycloak
  writes, stale owners cannot write after handoff, incomplete operations
  recover safely, and restart after `COMPLETE` leaves a user-changed password
  unchanged.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 19 |
| Critical | 4 |
| High | 14 |
| Medium | 1 |
| Low | 0 |
| Automated | 18 |
| Proposed automation | 1 |
| Manual | 0 |
| Behavioral PRD scope anchors with test cases | 7 / 7 |
| Interface changes with test cases | 5 / 5 |
