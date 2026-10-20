# Test Plan — OSAC-5137

## Overview

- **Feature:** Tenant-Scoped Service Account Management; tentative milestone 0.4.
- **Traceability:** The [PRD](prd.md)'s four In Scope bullets are IS-1–IS-4; it has no FR/NFR IDs. All four and all seven design interface changes have cases.
- **State:** 17 planned cases; no implementation tests run. An isolated Keycloak check passed for tenant claims and rotation. Repeatable component/E2E coverage still needs implementation and execution evidence; see [Gaps](#gaps).

## Test Cases

### IS-1: Tenant Admin lifecycle and role management through API, UI, and CLI

#### TC-IS1-01: Public API CRUD and deletion cleanup

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | critical | automated |

**Preconditions:** Two tenants; caller is Tenant A Admin.

**Steps:** Create an A account with `tenant-automation`; Get/List; update display name/description; Get; Delete; Get/List. Repeat Delete during a Keycloak outage, then restore it. In-process, pause reconciliation before Create, obtain a token, immediately Delete after commit, inspect finalizer/Get/List, try the token, then resume. Try supplying/removing finalizers through public input/masks.

**Expected Results:** Reads reflect creation/updates. Create persists the finalizer before any reconciliation. Delete retains the record with deletion timestamp/finalizer and denies its token with `PERMISSION_DENIED`, including during the outage or paused controller. Successful/retried cleanup removes the Keycloak client before archiving; Get then returns `NOT_FOUND` and List omits it. Input finalizers are ignored; finalizer masks return `INVALID_ARGUMENT`. Control reconciliation in-process; deployed cleanup polling is bounded to 120 seconds at 2-second intervals.

#### TC-IS1-02: Role grant/revoke and supported catalog

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | critical | automated |

**Preconditions:** A tenant account and assignable roles.

**Steps:** Grant `tenant-idp-manager`, remove all roles, then grant `tenant-automation` and `osac-csi-driver` individually; Get after each. Try removed `tenant-user`/`tenant-reader`, a provider role, and `realm-management`; try human RoleBindings for both machine-only roles.

**Expected Results:** Get reflects successful changes; empty roles grant no resource access. Forbidden updates return `INVALID_ARGUMENT` without changing grants. Human RoleBindings reject both machine-only roles.

#### TC-IS1-03: UI lifecycle and one-time credentials

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | high | automated |

**Preconditions:** Tenant Admin UI tests with mocked Connect responses.

**Steps:** Open list; create with a role; inspect/dismiss credentials; reload; edit metadata/roles; confirm rotation/deletion. Simulate lost create/rotate responses; navigate directly as Tenant User.

**Expected Results:** The picker offers `tenant-automation`, `tenant-idp-manager`, `tenant-admin`, and `osac-csi-driver` with public/private permissions and empty-role denial, never an implicit grant. Tenant/project/Keycloak IDs are not editable. List/detail show client ID, roles, and deletion state without secrets. Create/rotate secrets appear only in the immediate result and disappear on dismissal/reload, including from query cache. Rotation/deletion require confirmation. Uncertain responses prompt explicit regeneration without automatic retry. Tenant Users cannot manage accounts, including through direct navigation.

#### TC-IS1-04: Scriptable CLI lifecycle and roles

| Interface Change | Priority | Automation |
|---|---|---|
| IC-6 | high | automated |

**Preconditions:** Deployed Fulfillment and CLI from the same revision.

**Steps:** Non-interactively create, get, list, update metadata/roles from a file, rotate, and delete; parse output.

**Expected Results:** Successful commands exit zero with parseable output. Get/List/Update omit secret fields; create/rotate disclose their newly issued secret once.

#### TC-IS1-05: Failed creation leaves no active account

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | high | automated |

**Preconditions:** Inject Keycloak setup failure after client creation with cleanup available; separately inject DB commit failure after client enablement.

**Steps:** Create under each failure; inspect responses, Get/List, Keycloak, and logs. Remove the commit-failure orphan using its logged client ID.

**Expected Results:** Setup failure returns `UNAVAILABLE` and removes the partial client; commit failure returns `INTERNAL` and leaves an identifiable orphan for operator cleanup. Neither returns a secret or persists an account. Logs contain the generated client ID, never the secret.

### IS-2: Tenant and assigned-role isolation across OSAC services

#### TC-IS2-01: Tenant-filtered account lists and totals

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | critical | automated |

**Preconditions:** A/B each have an account and Tenant Admin.

**Steps:** List as each admin with pagination/totals.

**Expected Results:** Results and totals include only the caller's tenant.

#### TC-IS2-02: Cross-tenant account management

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2 | critical | automated |

**Preconditions:** B has an account; caller is Tenant A Admin.

**Steps:** Get/Update/Delete/RegenerateSecret using B's ID.

**Expected Results:** All return tenant-safe `NOT_FOUND`, disclose no B details/secrets, and leave B unchanged. A non-admin receives `PERMISSION_DENIED` before lookup.

#### TC-IS2-03: Token acquisition and cross-service tenant access

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | critical | automated |

**Preconditions:** Deployed Keycloak/Fulfillment; two A projects, one B project, and BMaaS/CaaS/VMaaS objects. A's account has `tenant-automation`, no human project membership. The client reaches and trusts both HTTPS issuer discovery and token endpoints.

**Steps:** Discover `token_endpoint` from the issuer's OIDC metadata; obtain a client-credentials token with TLS validation. Get/List A projects and permitted resources across both projects in each service. Repeat for B and nonexistent IDs.

**Expected Results:** Keycloak issues the token directly via HTTPS. It has exactly one signed string `osac_tenant=A`, the generated client ID as `azp`, and OSAC API audience. Both A projects/resources are accessible without memberships. Lists hide B; B Get matches a nonexistent resource's tenant-safe status/shape without disclosing data.

#### TC-IS2-04: Explicit grants and revocation

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-4 | critical | automated |

**Preconditions:** A account with no roles and an issued token; two A projects, an IdP, and a Secret with known raw data.

**Steps:** Try public reads/writes and private `Volumes/List`. Assign `tenant-automation`; read projects, write a permitted resource, List Secrets, and check self-access reviews. Replace with `tenant-idp-manager`, then `tenant-admin`; test each with the same unexpired token. Remove all roles and retry. Unit variants enumerate public/private RPCs, inject unrelated realm roles, and retain human/built-in CSI regressions.

**Expected Results:** No-role/unmapped calls return `PERMISSION_DENIED`. Automation permits resource writes/project reads but denies raw `Secrets/Get`, IdP/account management, and private Volumes. IdP manager adds IdP operations; admin adds raw Secret reads/account management. Secret List redacts `data`. All three deny private Volumes, Watch, and console sessions. Revocation applies without token refresh; permitted self-access reviews agree with actual calls. Realm claims add no permissions; B stays hidden.

#### TC-IS2-05: Deletion revokes an unexpired token

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | high | automated |

**Preconditions:** Active `tenant-automation` account with an unexpired token.

**Steps:** Delete; retry a formerly permitted method with that token.

**Expected Results:** `PERMISSION_DENIED` once `metadata.deletion_timestamp` is set, despite valid signature/expiry.

#### TC-IS2-06: Tenant input cannot select unrelated Keycloak clients

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2 | critical | automated |

**Preconditions:** Kind suite with a generated account and unrelated client whose settings/secret are recorded. The IDP principal has its existing organization/user roles plus only `create-client` and `manage-clients` as added `realm-management` roles.

**Steps:** Supply the unrelated ID in `status.client_id` on Create and display-metadata Update outside the mask; then try a status mask. Rotate/Delete using the real account ID, unrelated IDs, and cross-tenant IDs. Compare Keycloak state through the Admin API helper.

**Expected Results:** Create/display Update ignore input status and return the derived client ID; a status mask returns `INVALID_ARGUMENT` without an IDP call. Rotation/deletion target only the tenant-owned stored UUID. Unrelated settings/secret remain unchanged. The configured principal completes create, mapper, rotation, and deletion. This proves Fulfillment isolation; the principal itself retains realm-wide Keycloak access.

#### TC-IS2-07: Inline user-data visibility

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | high | automated |

**Preconditions:** ComputeInstance/BareMetalInstance fixtures in two A projects and B, with distinct credential-like inline `spec.user_data` markers. A has an automation account without human memberships and a Secret with another marker.

**Steps:** Get/List A/B resources; call A's `Secrets/Get`.

**Expected Results:** Both A inline markers are readable; B's resources/markers remain hidden. `Secrets/Get` returns `PERMISSION_DENIED` without `tenant-admin`: inline user data follows resource visibility, not Secret protection.

#### TC-IS2-08: Generic lifecycle with a private-API role

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-4 | critical | automated |

**Preconditions:** Real Fulfillment/PostgreSQL/Keycloak; A/B projects/volumes and valid storage tier; Tenant A Admin creates an account with only `osac-csi-driver`. No provider provisioning.

**Steps:** Obtain a token; Create/Get/List/Delete A volumes privately. Try B IDs, forged tenant metadata, input status, Volume Update/Signal, other private services, and public resource APIs. Add/revoke automation, then revoke CSI; retry API calls after each change with the same token. Regrant CSI, delete the account, and retry with that token.

**Expected Results:** CSI permits exactly four tenant-A Volume methods. Lists/totals exclude B; B Get/Delete return `NOT_FOUND`; foreign tenant metadata returns `PERMISSION_DENIED`. Create discards input status and persists server-derived values. Other methods are denied. Automation explicitly adds public permissions; removing it leaves only Volumes. Revoking all roles/deleting denies further resource calls immediately. Assert delete acceptance/state, not backend cleanup. Unit variants deny CSI permissions/wildcard tenancy from realm claims.

### IS-3: One-time disclosure and immediate secret replacement

#### TC-IS3-01: One-time creation secret and maximum client ID

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | critical | automated |

**Preconditions:** Tenant Admin; Kind suite also has a 63-character tenant name.

**Steps:** Create/Get/List/Update; inspect API/UI/CLI outputs and request/response logs with body logging enabled. Repeat logging checks for rotation; dry-run Create. Create for the maximum-length tenant and obtain a Keycloak token.

**Expected Results:** Create returns a derived client ID containing the authenticated tenant and persisted account UUID, plus one nonempty secret. Subsequent non-rotation responses and all logs contain no secret values. Dry-run calls no Keycloak and returns no secret. The 108-character client ID obtains a token.

#### TC-IS3-02: Rotation rejects the old secret but preserves issued tokens

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | critical | automated |

**Preconditions:** Real Kind Keycloak; active automation account with an unexpired token from its initial credentials. Keep roles unchanged.

**Steps:** Call a permitted API; rotate; repeat with the retained token; request tokens with old/new secrets; Get/List.

**Expected Results:** Rotation discloses one replacement; the retained token still works while unexpired. Old-secret token acquisition fails (isolated 26.6.4 result: `401 unauthorized_client`); the replacement obtains a token. Get/List disclose neither secret.

#### TC-IS3-03: Lost rotation response requires regeneration

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | high | automated |

**Preconditions:** Inject transport failure after Keycloak commits regeneration, before response delivery.

**Steps:** Get/List; explicitly regenerate again.

**Expected Results:** No secret readback; the second regeneration returns a different secret that obtains a token.

### IS-4: Tenant Admin and Tenant User documentation

#### TC-IS4-01: Management and token-use guidance

| Interface Change | Priority | Automation |
|---|---|---|
| IC-7 | high | manual |

**Preconditions:** Draft Tenant Admin/User guides.

**Steps:** Follow API/UI/CLI lifecycle, role, and rotation instructions as Admin; follow token/permitted-API examples as User.

**Expected Results:** Examples match shipped interfaces and discover Keycloak's HTTPS endpoint with TLS validation and `grant_type=client_credentials`. Guidance explains one-time secrets, old-secret rejection, retained-token validity, explicit roles/empty-role denial, restricted CSI Volumes, unavailable Watch/console, and OSAC-4197 ownership of CSI delivery/migration.

## Planning evidence and boundary matrix

Test paths below are proposed or extended by the implementing work. `[DEV]` owns Unit/component coverage and documentation; `[QE]` [OSAC-6557](https://redhat.atlassian.net/browse/OSAC-6557) owns E2E. Each case's assertions apply at the listed boundary; HTTP doubles do not establish Keycloak behavior.

| Behavior (requirements; interfaces) | Tier / cases / location | Command (working directory) | Real vs simulated; prerequisites |
|---|---|---|---|
| Public validation/tenancy/redaction (IS-1/2/3; IC-1/2/3) | Unit; TC-IS1-01/02/05, IS2-01/02/06, IS3-01; proposed `internal/servers/service_accounts_server_test.go` | `ginkgo run --timeout 10m internal/servers` (`fulfillment-service/`) | In-process server/test DB; mocked Keycloak. Inject commit failure, control reconciliation, and inspect derived/stored IDP targets. |
| Secret logging (IS-3; IC-1/2) | Unit; TC-IS3-01/02; extend `internal/logging/logging_interceptor_test.go` | `go test ./internal/logging` (`fulfillment-service/`) | Real proto serialization/body logger; both response types redacted. |
| Managed authorization (IS-2; IC-4) | Unit; TC-IS2-03/04/05/08; proposed `internal/auth/grpc_managed_client_test.go` and self-access review tests | `go test ./internal/auth ./internal/servers` (`fulfillment-service/`) | Real in-process policy/account lookup; simulated JWT/IDP/other services. Include unions, revocation, no `is_client`/`is_csi` fallback or wildcard tenancy, and Watch/console denial. |
| Private Volume tenancy/status (IS-2; IC-4) | Unit; TC-IS2-08; extend `internal/servers/private_volumes_server_test.go` | `ginkgo run --timeout 10m internal/servers` (`fulfillment-service/`) | In-process server/DAO/test DB; simulated identity/tier/provider dependencies. Real auth/API boundary below. |
| IDP calls/compensation/finalizers (IS-1/3; IC-1/2/3) | Unit; TC-IS1-01/02/05, IS3-02/03; proposed `internal/idp/service_account_client_test.go` and controller tests | `go test ./internal/idp ./internal/controllers/serviceaccount` (`fulfillment-service/`; controller package proposed) | HTTP double; tests handler compensation. Commit failure belongs to the public-server row. |
| CRUD/CLI/Keycloak contract (IS-1/2/3; IC-1/2/3/4/6) | Component integration; TC-IS1-01/02/04, IS2-01/02/03/06/07/08, IS3-01/02; proposed `it/it_service_accounts_test.go`, extending `it/it_tool.go` | `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` (`fulfillment-service/`; Kind required) | Real Fulfillment/PostgreSQL/Keycloak Admin API and token endpoint; existing `KeycloakAdminRequest` helper. Covers discovery/TLS, claims, maximum ID, rotation/retained token, client lifecycle/isolation, user data, and full private Volume CRUD with persisted volumes/tier fixture, without provider provisioning. |
| Tenant Admin UI (IS-1/3; IC-5) | Unit; TC-IS1-03, IS3-01; proposed co-located Vitest tests | `pnpm run typecheck && pnpm lint && pnpm test` (`osac-ui/`) | Real React components; mocked Connect. Live-browser harness remains manual, not persisted coverage. |
| Lifecycle/rotation/cross-service isolation (IS-1/2/3; IC-1/2/3/4) | E2E; TC-IS1-01/02, IS2-02/03/04/05/08, IS3-02; proposed `tests/e2e/regression/test_tenant_service_accounts.py` | `uv run pytest -n 0 tests/e2e/regression/test_tenant_service_accounts.py` (repo root) | Real Keycloak/Fulfillment and BMaaS/CaaS/VMaaS APIs; OpenShift `full-ci`. Reuse identity/CLI helpers; verify token TLS from the runner. For IS2-08, sample private Volume Get/List, cross-tenant denial, role removal/deletion; full private CRUD belongs above. |
| Documentation (IS-4; IC-7) | Manual; TC-IS4-01; proposed guides under `docs/` | Execute guide examples in a configured tenant; no automated command | Real UI/API/CLI. |

### E2E deployment and fixtures

Use `PLATFORM=openshift PROFILE=full-ci` with BMaaS/CaaS/VMaaS, Keycloak, and PostgreSQL. Select a disposable hub kubeconfig and `OSAC_NAMESPACE`; install `oc`, `kubectl`, `grpcurl`, and a compatible `osac` CLI. Deploy OSAC-6553/6554/6555 and OSAC-6366 changes; record image digests. [Codebase: `osac-installer/README.md`, `osac-installer/values/full-ci/{infra,instance}.yaml`]

OSAC-6557 owns fixtures beside `test_tenant_onboarding.py`: two tenants, two A projects/one B project, admins, IdP, Secret, tenant volumes, and persisted BMaaS/CaaS/VMaaS resources created through real APIs using profile catalogs/templates. Existing fixtures require tenant onboarding and ready default subnets. Tests check authorization without waiting for provider workload readiness. Cleanup removes only test-owned accounts/resources, then projects/tenants, with bounded waits and secret-free diagnostics.

Configure `OSAC_FULFILLMENT_ADDRESS`, `OSAC_FULFILLMENT_PRIVATE_ADDRESS`, `OSAC_KEYCLOAK_URL`, and credentials through existing fixtures. Reuse `tests/e2e/core/keycloak_admin.py` identity setup/CLI helpers, but add token acquisition that discovers HTTPS endpoints and verifies a trusted deployment CA; existing `curl -k` calls cannot prove TLS. Missing services/trust must fail the designated full-profile run.

Pytest configuration: `pyproject.toml`; fixtures: `tests/e2e/conftest.py` and `tests/e2e/regression/conftest.py`. Run the matrix's E2E command from the monorepo root after implementation. The proposed file has not run; OSAC-6557 must supply collection, deployed execution, and cleanup evidence.

## Gaps

### Requirement and interface coverage

All 4 requirements and 7 interfaces have planned coverage. Tenant claims, maximum client ID, discovery/TLS, and immediate old-secret rejection require real Keycloak; public/private grants and revocation require Fulfillment Unit/E2E coverage. TC-IS2-06 proves application targeting isolation, not Keycloak-level principal isolation.

### Execution readiness

- OSAC-6557 must implement/run the full-profile suite, resource fixtures, and TLS token helper; tenant-onboarding/JWT-auth tests provide reusable setup.
- `[DEV]` must add lifecycle cases to the existing real-Keycloak Kind suite and update `docs/INTEGRATION-TESTING.md` and the component touched-area map with the implementation.

## Summary

| Metric | Count |
|---|---:|
| Total test cases | 17 |
| Critical / high / medium / low | 10 / 7 / 0 / 0 |
| Automated / manual | 16 / 1 |
| Requirements with cases | 4 / 4 |
| Interface changes with cases | 7 / 7 |
