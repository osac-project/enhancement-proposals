# Testplan — OSAC-3027

## Overview

- **Feature:** OSAC-3027 — Request MFA Usage from Brokered OIDC Server
- **Total test cases:** 10
- **PRD In Scope bullets with API test cases:** 4 of 5
- **Interface changes with API test cases:** 3 of 5

IS-2's Tenant API authorization and persistence are tested, but its console
workflow is not. IS-4's user guidance has no API test boundary. Both remain
coverage gaps under the API-only test policy.

The PRD does not assign FR/NFR identifiers. This plan uses `IS-1` through
`IS-5` for its five ordered In Scope bullets and maps each test case back to
those anchors. The integration-testing coverage matrix below identifies the
owner, required tier, boundary, suite, command, and real versus simulated
dependencies for each behavior.

## Test Cases

### IS-1: Each Tenant has an independent MFA-request preference

#### TC-IS1-01: Tenant context maps to an optional upstream ACR value

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-1, IC-3 | Unit | [DEV] Fulfillment Service | critical | automated |

##### Preconditions

- A Tenant with the authentication-context field absent or empty.
- Tenant fixtures with a configured, provider-agreed authentication-context
  list containing one element and multiple elements.

##### Steps

1. Run Tenant field-validation and Keycloak URL-composition unit tests for an
   empty repeated field, one element, and multiple elements.
2. Repeat with an authorization URL containing unrelated query parameters and
   an `acr_values` entry the feature previously projected.
3. Repeat the TenantManager reconciliation tests with an authorization URL
   containing an out-of-band `acr_values` entry and a Tenant whose field was
   never configured.
4. Repeat the TenantManager reconciliation tests with the organization-scoped
   provider lookup returning 404 for the target alias.
5. Save a non-empty authentication-context value for a Tenant and clear it
   before reconciliation runs, with an out-of-band `acr_values` on its
   provider.
6. Force the two-writer order: pause the stale writer after it composes a
   provider update from the current Tenant and IdentityProvider versions;
   let the newer writer finish its update composed from advanced source
   versions, including its post-write check; then let the stale writer
   complete its PUT and post-write re-read, and run the next reconciliation
   pass.
7. Compose an update carrying forward unmanaged authorization URL
   parameters, then change the Keycloak-held `acr_values` directly between
   composition and the verification read.

##### Expected Results

- An absent or empty value adds no `acr_values` parameter.
- Configured repeated elements produce exactly one `acr_values` parameter,
  joined in order with single spaces after query decoding.
- Unrelated query parameters remain unchanged; an `acr_values` the feature
  previously projected is replaced by the configured Tenant value and removed
  when the field is cleared.
- An out-of-band `acr_values` on a provider the feature never configured is
  preserved unchanged and its authorization URL is not rewritten.
- When the organization-scoped lookup returns 404, reconciliation skips the
  provider and issues no realm-scoped update.
- A Tenant that saved and then cleared a value before reconciliation has
  still claimed ownership: reconciliation removes the out-of-band
  `acr_values` from its provider.
- The stale writer's post-write re-read detects the changed source versions
  even though the newer writer already completed its check; it requeues, and
  the next pass re-applies the state derived from the newer versions and
  restores both changes, so a write composed from a stale snapshot does not
  persist.
- The verify-before-write check detects the changed Keycloak-held value: the
  writer discards the composed update, recomposes from the fresh read, and
  does not overwrite the Keycloak-held edit.

#### TC-IS1-02: First [DEV] spike verifies the Keycloak propagation mechanism

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-3 | Component Integration | [DEV] Fulfillment Service | high | automated |

##### Preconditions

- A compatible Kind environment with deployed Fulfillment and Keycloak 26.6.4.
- Two OSAC Tenants with tenant-linked external OIDC providers created through
  the existing Fulfillment API; the test harness provides temporary external
  OIDC realms.
- No production Tenant authentication-context reconciliation code is assumed;
  configure the candidate ACR values on the test provider through the existing
  IdentityProvider configuration path.
- Tenant B never configures an authentication-context value, and its provider
  authorization URL carries an out-of-band `acr_values` configured through
  the same path.

##### Steps

1. Configure Tenant A's broker provider authorization URL with two ACR values
   and an unrelated query parameter; leave Tenant B's provider untouched with
   its out-of-band `acr_values`.
2. Start a fresh brokered login for each Tenant and capture both upstream
   authorization requests.
3. After each provider update, read both providers' configurations through
   the organization-scoped Keycloak endpoint.
4. Remove the ACR values from Tenant A's provider authorization URL and repeat
   Tenant A's fresh login.
5. Change Tenant B's Keycloak-held `acr_values` directly through the Keycloak
   administration API, then apply an unrelated update to Tenant B's provider
   through the existing IdentityProvider configuration path; read its
   configuration through the organization-scoped Keycloak endpoint and
   repeat Tenant B's fresh login.

##### Expected Results

- Tenant A's first upstream request contains exactly one `acr_values` parameter
  containing both values in order; its unrelated query parameter is preserved.
- Tenant B's request contains its out-of-band `acr_values`; the updates to
  Tenant A's provider do not disturb Tenant B's provider or its request.
- Tenant B's out-of-band `acr_values` survives its own provider update: the
  organization-scoped configuration still contains the value after the
  update, and Tenant B's repeated fresh login still carries it.
- The spike records how the direct Keycloak edit made before the update
  interacts with it — whether the changed value survives or is overwritten —
  and the gate records this with the mechanism evidence, because the design
  requires the verify-before-write check for production reconciliation.
- Each fresh brokered login completes through the updated provider; the
  provider's organization link and configured broker flows remain intact
  after each update.
- After clearing Tenant A's provider value, its upstream request contains no
  `acr_values` parameter.
- If any assertion fails, the spike gate fails: record the evidence and do not
  begin production reconciliation code until a supported mechanism is selected.

#### TC-IS1-03: Tenant reconciliation propagates distinct values to providers

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-1, IC-3 | Component Integration | [DEV] Fulfillment Service | critical | automated |

##### Preconditions

- A compatible Kind environment with deployed Fulfillment and Keycloak.
- Two OSAC Tenants: Tenant A with one tenant-linked external OIDC provider
  and Tenant B with one, created through Fulfillment; the test harness
  provides three temporary external realms, one reserved for a second
  Tenant A provider.
- Before reconciliation, Tenant A's initial provider carries an out-of-band
  `acr_values` in its authorization URL, configured through the existing
  IdentityProvider configuration path. Tenant B's never-configured provider
  carries an out-of-band `acr_values` and an unrelated query parameter that
  exist only in Keycloak, added directly through the Keycloak administration
  API.

##### Steps

1. Configure Tenant A with a provider-agreed authentication-context list and
   leave Tenant B's list empty.
2. Wait for Tenant reconciliation and complete a fresh brokered login for
   each Tenant.
3. Through the IdentityProvider API, edit Tenant A's existing provider and
   create a second tenant-linked OIDC provider for Tenant A; wait for
   reconciliation and complete a fresh brokered login through both.
4. Through the IdentityProvider API, apply an unrelated edit to Tenant B's
   provider; wait for reconciliation and complete a fresh brokered login
   for Tenant B.
5. Without waiting for the first change to reconcile, change Tenant A's
   authentication-context list and edit a linked provider's specification
   (for example, an unrelated authorization URL query parameter); wait for
   both reconciliations to settle and complete a fresh brokered login
   through each provider.
6. Clear Tenant A's list, wait for reconciliation, and start another fresh
   brokered login through each of Tenant A's providers.

##### Expected Results

- Tenant A's first upstream authorization request contains exactly one
  `acr_values` parameter with its configured values in order, replacing the
  seeded out-of-band value; Tenant B's request keeps its Keycloak-only
  out-of-band `acr_values` and carries no OSAC-projected parameter.
- Tenant B's Keycloak-only out-of-band `acr_values` and unrelated parameter
  survive its provider edit: after reconciliation, the Keycloak
  configuration still contains both and Tenant B's fresh login request
  still carries them.
- The edited provider and the newly created provider both receive the
  configured value; provider changes after the Tenant update do not remove
  the Tenant's setting.
- The overlapping updates converge with both changes applied: the request
  through the edited provider contains the provider's changed parameter and
  the new `acr_values` value, and neither reconciliation drops the other's
  change.
- Tenant A's later requests contain no `acr_values` value on either linked
  provider.
- Neither Tenant's provider configuration or request changes the other
  Tenant's setting.

### IS-2: Both administrator personas can change the setting in the console

#### TC-IS2-03: Tenant Admin is denied cross-Tenant and broad-spec updates

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-2 | Unit | [DEV] Fulfillment Service | critical | automated |

##### Preconditions

- The caller is a Tenant Admin for Tenant A.
- Tenant B exists and both Tenants have stored spec values.

##### Steps

1. Call public `Tenants.Update` for Tenant B with a mask targeting only the
   authentication-context field.
2. Call public `Tenants.Update` for Tenant A with mask `spec.domains`.
3. Read both Tenants using an authorized administrative client.

##### Expected Results

- The cross-Tenant update is denied and neither Tenant changes.
- The domains update is denied and Tenant A's domains remain unchanged.
- Tenant Admin updates with the own-Tenant authentication-context mask are
  allowed by authorization and server field-mask checks.

#### TC-IS2-05: Public Tenant Update persists only authorized auth changes

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-2 | Component Integration | [DEV] Fulfillment Service | critical | automated |

##### Preconditions

- A compatible deployed Fulfillment service, PostgreSQL, and Keycloak test
  identities are available.
- Tenant A and Tenant B exist; caller identities are Cloud Provider Admin,
  Tenant Admin A, and Tenant Admin B.
- Tenant A is seeded with domains and a break-glass reference.

##### Steps

1. Tenant Admin A updates Tenant A using public `Tenants.Update` with a mask
   targeting only the authentication-context field and lock enabled.
2. Perform a second authorized update of Tenant A's authentication-context
   field, then re-submit Tenant Admin A's original request with its now-stale
   version.
3. Tenant Admin A lists Tenants through the public API and reads Tenant A
   through the database-backed service.
4. Tenant Admin A attempts the same update against Tenant B.
5. Tenant Admin A attempts to update Tenant A's `spec.domains`.
6. Cloud Provider Admin updates Tenant B's authentication-context value.

##### Expected Results

- Tenant Admin A's own update is persisted and returned with the configured
  authentication-context value; Tenant A's domains and break-glass reference
  remain unchanged.
- The stale-version re-submission fails with a version conflict and does not
  change the stored Tenant, which still reflects the second update.
- Tenant Admin A's public list contains Tenant A and not Tenant B.
- Tenant Admin A's foreign-Tenant and domains updates are denied; neither
  Tenant's stored object changes for those requests.
- Cloud Provider Admin's update to Tenant B is persisted.

### IS-3: MFA request is best effort; disabled preserves current sign-in

#### TC-IS3-01: Upstream provider ignores the request and login follows its policy

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-3 | Component Integration | [DEV] Fulfillment Service | high | automated |

##### Preconditions

- A compatible Kind environment and the existing temporary external OIDC
  realm fixture.
- The external provider accepts the authorization request but does not
  require MFA.

##### Steps

1. Configure the Tenant's authentication-context value.
2. Run the existing brokered OIDC authorization-code flow through Keycloak.
3. Have the external provider authenticate according to its normal policy.

##### Expected Results

- The upstream request contains the configured ACR value.
- Keycloak completes the broker login and returns a non-empty OSAC token.
- OSAC does not reject the login or report that MFA was performed.

#### TC-IS3-02: Empty authentication context omits the upstream parameter

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-1, IC-3 | Component Integration | [DEV] Fulfillment Service | critical | automated |

##### Preconditions

- A Tenant with an absent or empty authentication-context field that was
  never configured, and a READY, tenant-linked OIDC provider in the deployed
  Keycloak realm whose authorization URL carries no out-of-band `acr_values`.

##### Steps

1. Complete a fresh brokered OIDC login.
2. Capture the request received by the temporary external OIDC realm.

##### Expected Results

- The upstream authorization request has no `acr_values` key.
- The login follows the existing broker flow and returns a non-empty OSAC
  token.

#### TC-IS3-03: Invalid ACR elements and unsupported update masks are rejected

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-1, IC-2 | Unit | [DEV] Fulfillment Service | high | automated |

##### Preconditions

- Fulfillment proto validation and public Tenant server test fixtures are
  available.

##### Steps

1. Submit an empty repeated element and an element containing whitespace.
2. Submit an update mask that includes the repeated authentication-context
   field and `spec.domains`, then one targeting only `spec.domains`, then a
   request with no update mask.
3. Submit a syntactically valid but unrecognized identifier and read the Tenant
   from a separate transaction.

##### Expected Results

- Invalid elements return `InvalidArgument`; unsupported and omitted masks are
  rejected. No rejected request changes the stored Tenant.
- The syntactically valid identifier is stored and sent unchanged; provider
  interpretation is outside OSAC validation.

#### TC-IS3-04: Upstream ACR rejection surfaces the broker error

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-3 | Component Integration | [DEV] Fulfillment Service | high | automated |

##### Preconditions

- The deployed Keycloak broker and temporary external OIDC realm are available.
- The temporary external-realm fixture is extended to return an OIDC
  authorization error when it receives the configured ACR request.
- The Tenant has a non-empty authentication-context value and its linked
  provider is READY.

##### Steps

1. Start a fresh brokered login for the Tenant.
2. Have the external realm capture the authorization request and return its
   configured OIDC error.
3. Observe the broker login result and captured upstream requests.

##### Expected Results

- The upstream request contains the configured Tenant value.
- The broker login returns an error and no OSAC token is issued.
- Keycloak/OSAC does not issue a second upstream request with `acr_values`
  removed.

### IS-4: Tenant Admin guidance describes limits of the request

No API-only test is defined for this guidance requirement; it remains an
uncovered gap under the API-only test scope.

### IS-5: Cloud Infrastructure Admin can verify the request during sign-in

#### TC-IS5-01: Captured upstream request shows the configured ACR

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-3 | Component Integration | [DEV] Fulfillment Service | high | automated |

##### Preconditions

- The existing `Identity provider login flow` integration fixture runs with a
  temporary external OIDC realm that can capture its authorization request.
- The Tenant has a configured authentication-context value and the external
  realm is linked through Fulfillment and Keycloak.

##### Steps

1. Start a fresh brokered sign-in through the tenant-specific Keycloak IdP.
2. Inspect the captured request at the external realm.

##### Expected Results

- The captured request contains exactly one `acr_values` parameter with the
  configured Tenant value.
- The returned OSAC token or UI does not assert that MFA was completed.

## Coverage Matrix

| Owner / touched behavior | Requirement / interface | Tier and required boundary | Test case(s) | Suite / location | Command, working directory, prerequisites | Real vs. simulated |
|---|---|---|---|---|---|---|
| [DEV] Fulfillment API, authorization, and reconciliation helpers | IS-1, IS-2, IS-3; IC-1, IC-2, IC-3 | Unit: message validation, Tenant server update, OPA method decision, URL composition, and reconcile behavior | TC-IS1-01, TC-IS2-03, TC-IS3-03 | `fulfillment-service/internal/servers`, `internal/auth`, `internal/controllers/tenant`, `internal/controllers/identityprovider`, `internal/idp` | From `fulfillment-service/`: `ginkgo run --timeout 20m -r internal` (documented full internal-unit command; no cluster required). | Go, proto validation and test database fixtures run; Keycloak admin client/external OP are mocked. |
| [DEV] Public Tenant Update authorization and persistence | IS-2; IC-2 | Component integration: deployed Fulfillment API, PostgreSQL, and Keycloak-authenticated identities | TC-IS2-05 | Proposed `fulfillment-service/it/it_tenants_auth_context_test.go` | From repository root: `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`. Requires the documented compatible Kind environment. | Deployed Fulfillment, PostgreSQL, and Keycloak authentication are real; tenant fixtures and test accounts are created by the harness. |
| [DEV] Keycloak propagation research/spike — first implementation task | IS-1, IS-5; IC-3 | Component integration: deployed Fulfillment + PostgreSQL + Keycloak 26.6.4 + external OIDC authorization endpoint | TC-IS1-02 | Extend `fulfillment-service/it/it_identity_providers_login_test.go` using existing IdentityProvider configuration, before production Tenant reconciliation changes | From repository root: `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`. Requires a compatible disposable Kind environment; focused run: `ginkgo run --timeout 20m --focus 'Identity provider login flow' it` from `fulfillment-service/`. | Real Fulfillment, PostgreSQL, Keycloak and external OIDC realm. The spike records whether the configured-URL candidate passes; failure blocks production implementation and returns mechanism selection to design. |
| [DEV] Tenant-specific Keycloak reconciliation | IS-1, IS-3, IS-5; IC-1, IC-3 | Component integration: deployed Fulfillment + PostgreSQL + Keycloak + external OIDC authorization endpoint | TC-IS1-03, TC-IS3-01, TC-IS3-02, TC-IS3-04, TC-IS5-01 | Extend `fulfillment-service/it/it_identity_providers_login_test.go` and its temporary external-realm fixture after the spike selects a mechanism | From repository root: `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`. Requires a compatible disposable Kind environment; focused run: `ginkgo run --timeout 20m --focus 'Identity provider login flow' it` from `fulfillment-service/`. | Fulfillment, PostgreSQL and Keycloak run for real; the temporary external realm is test-controlled. Its ACR-rejection response behavior is a proposed fixture extension and is not currently exercised. No workload operator/provider provisioning. |

### Requirement Coverage Gaps

API test cases cover four of the five PRD In Scope bullets. IS-2's Tenant API
authorization and persistence are tested, but the console workflow is not;
IS-4's guidance requirement has no API test boundary. Both remain unresolved
coverage gaps under the API-only policy. The upstream-ACR-rejection case also
requires a fixture extension that is not yet implemented; no separate owner
ticket is identified, so that test boundary is unresolved until the fixture is
added.

### Interface Change Coverage Gaps

Three of five interface changes have API test cases. IC-4's console workflow
and IC-5's documentation change have no API test boundary and remain uncovered;
they are not reported as covered.

## Summary

| Metric | Count |
|---|---:|
| Total test cases | 10 |
| Critical | 5 |
| High | 5 |
| Medium | 0 |
| Low | 0 |
| Automated | 10 |
| Manual | 0 |
| Requirements with API test cases | 4 / 5 |
| Interface changes with API test cases | 3 / 5 |
