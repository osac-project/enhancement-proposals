# Testplan — OSAC-3027

## Overview

- **Feature:** OSAC-3027 — Request MFA Usage from Brokered OIDC Server
- **Total test cases:** 15
- **Requirements covered:** 5 of 5 PRD In Scope bullets
- **Interface changes covered:** 5 of 5

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
   an existing `acr_values` entry.

##### Expected Results

- An absent or empty value produces no `acr_values` parameter.
- Configured repeated elements produce exactly one `acr_values` parameter,
  joined in order with single spaces after query decoding.
- Unrelated query parameters remain unchanged; any existing `acr_values` is
  replaced by the configured Tenant value or removed when the field is empty.

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

##### Steps

1. Configure Tenant A's broker provider authorization URL with two ACR values
   and an unrelated query parameter; leave Tenant B's provider without ACR
   values.
2. Start a fresh brokered login for each Tenant and capture both upstream
   authorization requests.
3. Remove the ACR values from Tenant A's provider authorization URL and repeat
   Tenant A's fresh login.

##### Expected Results

- Tenant A's first upstream request contains exactly one `acr_values` parameter
  containing both values in order; its unrelated query parameter is preserved.
- Tenant B's request contains no `acr_values`, and Tenant A's provider setting
  does not alter Tenant B's request.
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
- Two OSAC Tenants, each with a tenant-linked external OIDC provider created
  through Fulfillment; the test harness provides two temporary external realms.

##### Steps

1. Configure Tenant A with a provider-agreed authentication-context list and
   leave Tenant B's list empty.
2. Wait for Tenant reconciliation and complete a fresh brokered login for
   each Tenant.
3. Clear Tenant A's list, wait for reconciliation, and start another fresh
   brokered login for Tenant A.

##### Expected Results

- Tenant A's first upstream authorization request contains exactly one
  `acr_values` parameter with its configured values in order; Tenant B's
  request contains none.
- Tenant A's later request contains no `acr_values` value.
- Neither Tenant's provider configuration or request changes the other
  Tenant's setting.

### IS-2: Both administrator personas can change the setting in the console

#### TC-IS2-01: Cloud Provider Admin changes one Tenant's setting

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-2, IC-4 | Unit | [UI] osac-ui | critical | automated |

##### Preconditions

- Tenant list fixtures include two Tenants.
- The session role is Cloud Provider Admin.

##### Steps

1. Open Tenant A's authentication settings from the Tenants page.
2. Enter provider-agreed ACR values as separate list entries and save.
3. Inspect the Connect request sent by the UI.

##### Expected Results

- The page identifies Tenant A and shows an empty value when no request is
  configured.
- The update contains only the TenantSpec authentication-context field and the
  current object version; each identifier is a separate repeated element.
- Tenant B's displayed value is unchanged.

#### TC-IS2-02: Tenant Admin changes only their own Tenant

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-2, IC-4 | Unit | [UI] osac-ui | critical | automated |

##### Preconditions

- The session role is Tenant Admin and `tenantId` identifies Tenant A.
- Tenant fixtures include Tenant A and a different Tenant B.

##### Steps

1. Open `/tenant/settings/authentication`.
2. Enter provider-agreed ACR values as separate list entries and save.
3. Inspect the displayed Tenant and the Connect update request.

##### Expected Results

- The page displays Tenant A only and submits an update for Tenant A.
- The update mask contains only the TenantSpec authentication-context field;
  identifiers are submitted as separate repeated elements.
- The UI offers no Tenant B selector or cross-Tenant action.

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

#### TC-IS2-04: Tenant Admin changes the setting in a deployed console flow

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-2, IC-3, IC-4 | QE E2E | [QE] OSAC E2E | critical | manual |

##### Preconditions

- A deployed OSAC console, Fulfillment API, PostgreSQL, Keycloak, and
  tenant-scoped external OIDC provider are available.
- A Tenant Admin can sign in to Tenant A; Tenant B is a separate tenant.

##### Steps

1. As Tenant Admin for Tenant A, open `/tenant/settings/authentication`, enter
   provider-agreed ACR values as separate list entries, and save.
2. Start a fresh brokered sign-in for Tenant A and inspect the upstream
   provider's authorization-request log.
3. Repeat for Tenant B with its authentication-context field empty.

##### Expected Results

- Tenant A's saved value appears in exactly one upstream `acr_values`
  parameter.
- Tenant B's field remains empty and its upstream request has no
  `acr_values` parameter.
- Neither tenant's sign-in is described by OSAC as proof that MFA occurred.

#### TC-IS2-05: Public Tenant Update persists only authorized auth changes

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-2 | Component Integration | [DEV] Fulfillment Service | critical | automated |

##### Preconditions

- A compatible deployed Fulfillment service, PostgreSQL, and Keycloak test
  identities are available.
- Tenant A and Tenant B exist; caller identities are Cloud Provider Admin,
  Tenant Admin A, and Tenant Admin B.

##### Steps

1. Tenant Admin A updates Tenant A using public `Tenants.Update` with a mask
   targeting only the authentication-context field and lock enabled.
2. Tenant Admin A lists Tenants through the public API and reads Tenant A
   through the database-backed service.
3. Tenant Admin A attempts the same update against Tenant B.
4. Tenant Admin A attempts to update Tenant A's `spec.domains`.
5. Cloud Provider Admin updates Tenant B's authentication-context value.

##### Expected Results

- Tenant Admin A's own update is persisted and returned with the configured
  authentication-context value.
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

- A Tenant with an absent or empty authentication-context field and a READY,
  tenant-linked OIDC provider in the deployed Keycloak realm.

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
2. Submit an update mask that includes the repeated authentication-context field and
   `spec.domains`, then one targeting only `spec.domains`.
3. Submit a syntactically valid but unrecognized identifier and read the Tenant
   from a separate transaction.

##### Expected Results

- Invalid elements return `InvalidArgument`; unsupported masks are rejected.
  No rejected request changes the stored Tenant.
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

#### TC-IS4-01: UI guidance says the provider decides MFA

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-4 | Unit | [UI] osac-ui | high | automated |

##### Preconditions

- The Tenant Admin authentication-settings page and its explanatory copy are
  implemented.

##### Steps

1. Render the page as Tenant Admin with a configured value and with the field
   empty.

##### Expected Results

- The page says OSAC sends the configured value as an optional request, the
  tenant-managed provider decides how to honor it, and OSAC does not guarantee
  MFA.
- The page tells admins to use values agreed with their provider and to clear
  the field to disable the request. Identifiers are entered as separate list
  entries; the upstream request serializes them as space-delimited `acr_values`.
- The page does not claim that a particular sign-in completed MFA.

#### TC-IS4-02: Tenant identity guide documents the best-effort request

| Interface Change | Tier | Owner | Priority | Automation |
|---|---|---|---|---|
| IC-5 | Manual documentation review | [DEV] Fulfillment Service | medium | manual |

##### Preconditions

- The Tenant identity and access guide contains the MFA request section.

##### Steps

1. Review `docs/guides/tenant-identity-and-access-guide.md` against PRD
   decisions D2, D3, and D5.

##### Expected Results

- The guide states the request is optional, the provider chooses its response,
  and OSAC does not guarantee or report MFA completion.
- The guide explains that configured values must be agreed with the provider
  to request generic MFA, that an empty list sends no request, and that OSAC
  does not validate provider-specific meaning.
- The guide provides a verification approach using upstream provider request
  logs or a fresh browser broker redirect.

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
| [UI] Console setting screens | IS-2, IS-4; IC-4 | Unit: React component behavior and payload against Connect mock transport | TC-IS2-01, TC-IS2-02, TC-IS4-01 | New/extended Tenant settings component tests under `osac-ui/libs/ui-components/src/components/Tenant/` | From `osac-ui/`: `pnpm test`. No live service required; tests use `createMockConnectTransport`. | UI components and mock API transport run; authentication/authorization and backend persistence are simulated. |
| [DEV] Tenant identity documentation | IS-4; IC-5 | Manual documentation review; no runtime boundary | TC-IS4-02 | `docs/guides/tenant-identity-and-access-guide.md` | Review the Markdown diff; no test command. Documentation-only behavior has no runtime integration boundary. | Human review; no services are run. |
| [QE] Deployed console-to-broker user journey | IS-2, IS-3, IS-5; IC-2, IC-3, IC-4 | QE E2E: console update, persisted Tenant setting, fresh Keycloak broker request to external OIDC provider | TC-IS2-04 | No persisted browser feature E2E currently exists. A new QE-owned deployed test/harness is needed; `tests/e2e/regression/test_tenant_onboarding.py` does not exercise the OSAC console. | No runnable command is defined for a persisted browser test. Record as unresolved until QE identifies an owner, ticket, and harness. Manual UI testing requires an already-deployed OSAC UI and configured external OIDC provider and is not persistent regression coverage. | Would need deployed OSAC UI, Fulfillment, PostgreSQL, Keycloak, and external OIDC test provider all running; none is proven by UI unit tests. |

### Requirement Coverage Gaps

All five PRD In Scope bullets have planned behavioral test cases. The deployed
console-to-broker QE E2E boundary is not execution-ready: no persisted browser
suite, owner ticket, or runnable command is identified. This is unresolved and
is not covered by UI unit or Fulfillment component-integration tests. The
upstream-ACR-rejection case also requires a fixture extension that is not yet
implemented; no separate owner ticket is identified, so that test boundary is
unresolved until the fixture is added.

### Interface Change Coverage Gaps

All five interface changes have test cases. IC-4's deployed UI journey is only
covered by UI unit tests until the QE E2E gap above is resolved; it is not
reported as deployed coverage.

## Summary

| Metric | Count |
|---|---:|
| Total test cases | 15 |
| Critical | 8 |
| High | 6 |
| Medium | 1 |
| Low | 0 |
| Automated | 13 |
| Manual | 2 |
| Requirements with test cases | 5 / 5 |
| Interface changes with test cases | 5 / 5 |
