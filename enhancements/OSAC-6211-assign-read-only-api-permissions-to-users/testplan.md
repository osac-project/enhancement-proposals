# Testplan — OSAC-6211

## Overview

- **Feature:** OSAC-6211 — Assign read-only API permissions to users
- **Total test cases:** 10
- **Requirements covered:** 2 of 2 draft trace references
- **Interface changes covered:** 4 of 4

The PRD has no requirement IDs. FR-1 maps to its first In Scope bullet; FR-2
maps to its second. These labels exist only to trace this testplan to the PRD.

## Test Cases

### FR-1: Reader roles add Get, List, and Watch grants within existing access scope

#### TC-FR1-01: Apply reader method grants and combine explicit role grants

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-1 | critical | automated | Unit | Fulfillment Service [DEV] |

##### Preconditions

- The OPA policy test inputs include a reader-only identity for each seeded
  reader role, an identity with both `tenant-reader` and `tenant-admin`, and a
  non-reader general-client identity.
- The existing `tenant-admin` policy grants
  `/osac.public.v1.Clusters/Create`,
  `/osac.public.v1.Clusters/Update`, and
  `/osac.public.v1.Clusters/Delete`.
- The non-reader client identity receives the existing implicit general-client
  fallback.
- The reviewed reader path list includes at least
  `/osac.public.v1.Clusters/Get`,
  `/osac.public.v1.Clusters/List`, and
  `/osac.public.v1.Events/Watch`.

##### Steps

1. Enumerate registered public and private gRPC methods and evaluate the
   aggregate decision for each reader-only identity on each method path.
2. Evaluate `/osac.public.v1.Clusters/Create`,
   `/osac.public.v1.Clusters/Update`, and
   `/osac.public.v1.Clusters/Delete` for the identity with both
   `tenant-reader` and `tenant-admin`.
3. Evaluate `/osac.public.v1.Clusters/Create` for the non-reader
   general-client identity.
4. Evaluate `GetByName`, `ListServices`, and `WatchSomething`, plus health
   and reflection paths, for the reader-only identity.

##### Expected Results

- A reader-only identity is allowed only on explicitly reviewed paths, and
  every such path ends in exactly `Get`, `List`, or `Watch`.
- Both reader roles add the same reviewed method grants; neither role adds
  Create, Update, or Delete.
- Neither reader-only identity receives the implicit general-client fallback
  or default metadata, health, and reflection allows. Its OPA decision has
  `Allowed=false` for every method outside its reviewed reader paths,
  including Create, Update, Delete, `GetByName`, `ListServices`,
  `WatchSomething`, and Signal.
- `tenant-admin` still allows Create, Update, and Delete when assigned with
  `tenant-reader`; the reader role does not remove that role's permissions.
- The non-reader identity retains its existing grant for
  `/osac.public.v1.Clusters/Create` through the general-client fallback.

#### TC-FR1-02: Watch only streams events visible to the reader's tenant

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-1 | critical | automated | Component integration | Fulfillment Service [DEV] |

##### Preconditions

- A container runtime is available to start the Kafka test container.
- The integration environment has events for `tenant-a` and `tenant-b`.
- The test user has a `tenant-reader` token scoped to `tenant-a`.

##### Steps

1. Use the public gRPC client with the reader token to call
   `/osac.public.v1.Events/Watch` through the authorization interceptor.
2. Publish one event for `tenant-a` and one event for `tenant-b`.
3. Collect events from the Watch stream.

##### Expected Results

- The stream contains the event for the reader's tenant.
- The stream contains no event belonging to `tenant-b`.
- The call passes reader authorization and the existing tenant filter.

#### TC-FR1-03: Keep reader reads within the tenant scope

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-1 | critical | automated | Component integration | Fulfillment Service [DEV] |

##### Preconditions

- Fulfillment Service, PostgreSQL, and Keycloak are deployed using the
  documented fulfillment integration profile.
- The token has the `tenant-reader` role and tenant claim `tenant-a`.
- Clusters `cluster-tenant-a` and `cluster-tenant-b` exist in tenants
  `tenant-a` and `tenant-b`, respectively.

##### Steps

1. Call `/osac.public.v1.Clusters/Get` for
   `cluster-tenant-a`, then call `/osac.public.v1.Clusters/List`.
2. Call `/osac.public.v1.Clusters/Get` for the known
   `cluster-tenant-b` object.

##### Expected Results

- Get returns `cluster-tenant-a`, and List contains only objects visible in
  `tenant-a`.
- Get for `cluster-tenant-b` returns `NOT_FOUND`, as required by the
  existing tenant-filtered Get contract.
- No object from `tenant-b` appears in the List response.

#### TC-FR1-04: Map a reader token to the reader UI session role

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-3 | high | automated | Unit | OSAC UI [DEV] |

##### Preconditions

- The UI session test has token claims for `tenant-reader` and
  `cloud-provider-reader`, each without an administrative role.

##### Steps

1. Pass each role claim through the session role mapper.
2. Inspect the resulting UI session role.

##### Expected Results

- The session role is reader.
- The role mapper does not classify the user as tenant-user or an
  administrator.

#### TC-FR1-05: Keep cloud-provider-reader within the user's provider scope

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-1 | critical | automated | Component integration | Fulfillment Service [DEV] |

##### Preconditions

- Fulfillment Service, PostgreSQL, and Keycloak are deployed using the
  documented fulfillment integration profile.
- The token has the `cloud-provider-reader` role and the user's existing
  provider authorization scope.
- Cluster `cluster-provider-in-scope` is visible in that scope, and
  `cluster-provider-out-of-scope` is outside it.

##### Steps

1. Call `/osac.public.v1.Clusters/Get` for
   `cluster-provider-in-scope`.
2. Call `/osac.public.v1.Clusters/Get` for
   `cluster-provider-out-of-scope`.
3. Call `/osac.public.v1.Clusters/List` and inspect the returned clusters.

##### Expected Results

- Get returns `cluster-provider-in-scope`.
- Get for `cluster-provider-out-of-scope` returns `NOT_FOUND`, matching the
  existing scope-filtered Clusters/Get contract in TC-FR1-03.
- List contains only clusters in the user's existing provider scope; the
  reader role adds no tenant or provider visibility.

#### TC-FR1-06: Deny reader-only mutations through the public gRPC interceptor

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-1 | critical | automated | Component integration | Fulfillment Service [DEV] |

##### Preconditions

- Fulfillment Service, PostgreSQL, and Keycloak are deployed using the
  documented fulfillment integration profile.
- The test user has a refreshed JWT with `tenant-reader` and no other explicit
  role or admin grant for methods outside the reviewed read list.
- `cluster-reader-denial` exists in the user's tenant with a three-node
  node set for Update and Delete checks. A valid Create fixture is available.

##### Steps

1. Use the public gRPC client with the reader JWT to call
   `/osac.public.v1.Clusters/Get` for `cluster-reader-denial` and call
   `/osac.public.v1.Clusters/List` through the authorization interceptor.
2. Call `/osac.public.v1.Clusters/Create` with an otherwise-valid Cluster
   using a new metadata name, call Update for `cluster-reader-denial` with
   its node-set size changed from 3 to 4, then call Delete for that cluster.
3. Use an authorized test identity to check whether the Create, Update, or
   Delete calls changed persisted state.

##### Expected Results

- The in-scope Get and List calls succeed and retain existing tenant filtering.
- The public gRPC interceptor returns `PERMISSION_DENIED` for Create, Update,
  and Delete before any handler changes a resource.
- The Create request persists no resource; `cluster-reader-denial` remains
  unchanged and present after the rejected Update and Delete calls.

### FR-2: Authorized administrators can assign reader roles through the API and UI, and documentation explains additive access

#### TC-FR2-01: Assign a reader role and verify old/refreshed token access

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-2 | critical | automated | Component integration | Fulfillment Service [DEV] |

##### Preconditions

- The documented fulfillment integration profile has Fulfillment Service,
  PostgreSQL, and Keycloak running.
- An authorized administrator and test users for `tenant-reader` and
  `cloud-provider-reader` exist.
- Each test user has no other explicit role or admin grant for methods
  outside the reviewed read list.
- The users can obtain an access token and refresh that same token session.
- `cluster-reader-denial` exists in scope for each user with a three-node
  node set. A valid Cluster Create fixture and unique metadata names are ready.

##### Steps

1. Obtain an access token and refresh token for each user before role
   assignment. Through the public gRPC API, call Clusters/Get for
   `cluster-reader-denial` and Clusters/Create with a valid Cluster fixture
   and unique metadata name; confirm both calls succeed.
2. Create a RoleBinding through the existing API for each seeded role:
   `tenant-reader` and `cloud-provider-reader`.
3. Wait for each RoleBinding status to become READY.
4. Send the original access token through the public gRPC API after READY.
   Call Clusters/Get and Clusters/Create with that same token, using a new
   unique name for Create.
5. Refresh each token using its refresh token, inspect the new JWT for the
   assigned reader role. With the refreshed JWT, call Clusters/Get for
   `cluster-reader-denial`, Create with another unique metadata name, Update
   that cluster with its node-set size changed from 3 to 4, and Delete it,
   all through the public gRPC API.
6. Remove any resources created with the original tokens using the authorized
   administrator identity.

##### Expected Results

- The API creates both RoleBindings and returns their resource identities.
- Each RoleBinding reaches READY after Keycloak synchronization.
- The original token retains its pre-assignment claims and can still Get and
  Create after READY; READY does not invalidate active tokens.
- Each refreshed JWT contains the assigned reader role. A reader role prevents
  the implicit general-client fallback from applying to that identity.
- The refreshed token can Get an in-scope cluster. Create, Update, and Delete
  return `PERMISSION_DENIED` for the reader-only user. These rejected calls
  make no persisted changes; only the authorized old-token Create calls
  create resources before cleanup.

#### TC-FR2-02: Assign a reader role in the Role Bindings UI

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-3 | high | automated | Unit | OSAC UI [DEV] |

##### Preconditions

- The UI test has an administrator session and API fixtures containing a
  `tenant-reader` role, a `cloud-provider-reader` role, and eligible users.

##### Steps

1. Open the Role Bindings page and start creating a binding.
2. Select each reader role and its eligible user, then submit both forms.

##### Expected Results

- Both reader roles appear by their configured titles in the role selector.
- Each submitted RoleBinding request contains the selected role and user.
- The UI displays both returned bindings and their synchronization status.

#### TC-FR2-03: Assign through the UI and view an authorized object as a reader

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-2, IC-3 | critical | manual | E2E | OSAC QE |

##### Preconditions

- A deployed OSAC environment has the UI, Fulfillment Service, PostgreSQL,
  and Keycloak available.
- An administrator session and a tenant user's active browser session are
  available; the tenant has a resource the user may read.
- The tenant user has no other explicit role or admin grant for methods
  outside the reviewed read list.
- The manual browser harness can keep the tenant session open while the
  administrator assigns the role and can use the tenant session's refresh
  token after READY.
- Cluster `cluster-reader-ui` has a node set with size 3 for the denied Update
  and Delete checks; a valid Create fixture is available.

##### Steps

1. Sign in as the tenant user and keep that browser session open.
2. Sign in as the administrator and assign `tenant-reader` in the UI.
3. Wait for the RoleBinding to show READY, then refresh the tenant user's
   access token in the existing session using its refresh token.
4. Open an authorized object as the reader.
5. Check the reader's navigation and object actions for Create, Update, and
   Delete controls.
6. Call `/osac.public.v1.Clusters/Create` with a valid Cluster and unique
   metadata name, call Update for `cluster-reader-ui` changing its node-set
   size from 3 to 4, then call Delete for that cluster, all through the public
   API with the refreshed reader token.

##### Expected Results

- The assignment reaches READY.
- The refreshed token contains `tenant-reader`, and the UI maps it to the
  reader session role.
- The reader session displays the authorized object and no object outside its
  tenant scope.
- The UI hides Create, Update, and Delete controls for the reader.
- The direct mutation calls return `PERMISSION_DENIED`; the reader-only
  account does not receive the implicit general-client fallback.
- This manual flow is not persisted regression coverage; OSAC QE follow-up
  work must be created during decomposition.

#### TC-FR2-04: Check user-facing API and UI permission guidance

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-4 | medium | manual | Manual documentation review (not a runtime test tier) | Fulfillment Service [DEV] |

##### Preconditions

- The updated tenant identity and access guide is available in the change
  under review.

##### Steps

1. Read the guide's API and UI assignment instructions.
2. Check the guide's `Read-only API access` section for both role names,
   assignment paths, allowed method names, token refresh timing, UI behavior,
   and existing tenant/provider scope.

##### Expected Results

- The section names `tenant-reader` and `cloud-provider-reader`, and describes
  the reviewed `Get`, `List`, or `Watch` grants.
- The section explains that a reader role skips the implicit general-client
  fallback, while grants from other explicitly assigned roles remain
  additive. Existing tenant and provider scope still applies.
- The section explains API and UI assignment, hidden mutation controls, and
  that READY means Keycloak sync; users refresh their token to update its
  claims.

## Graduation Criteria

- Policy unit tests enumerate registered gRPC methods and verify that a
  reader-only identity is allowed only on reviewed paths ending in exactly
  `Get`, `List`, or `Watch`. They verify the implicit general-client fallback
  is skipped for reader identities, explicit role grants remain additive,
  and non-reader client fallback behavior is unchanged.
- Component integration tests verify tenant and provider scope, Watch filtering
  through the public gRPC interceptor, out-of-scope Get behavior, and
  `PERMISSION_DENIED` with no mutation for reader-only Create, Update, and
  Delete calls.
- RoleBinding tests verify both seeded roles, READY after Keycloak sync, old
  token access after READY, and refreshed-token calls through the public gRPC
  interceptor with reader-only mutation denials.
- UI tests map both reader roles to the reader session; UI acceptance confirms
  mutation controls are hidden.
- User documentation covers the reader grants, the general-client fallback
  exception, additive explicit role grants, existing scope, refresh timing,
  and UI behavior.
- Before release, OSAC QE either adds persisted E2E regression coverage or
  records an explicit acceptance of the manual-only gap.

## Test Execution Evidence

| Case | Owning component and behavior | Required tier and boundary | Suite or proposed location | Command, workdir, and prerequisites | Real and simulated dependencies | Execution readiness and owner |
|------|-------------------------------|----------------------------|---------------------------|-----------------------------------|-------------------------------|-------------------------------|
| TC-FR1-01 | Fulfillment Service: reader grants, fallback exclusion, and tenant-admin role permissions | Unit; policy evaluator with reader-only, tenant-reader plus tenant-admin, and non-reader inputs | Extend fulfillment-service/internal/auth/authorization_evaluator_test.go | ginkgo run -r internal from fulfillment-service/; no cluster required, but the recursive suite requires a container runtime | OPA runs in process; method paths and identity claims are test controlled | Existing unit suite; Fulfillment Service [DEV] |
| TC-FR1-02 | Fulfillment Service: reader Watch authorization and tenant filtering | Component integration; public Events/Watch call through interceptor and Kafka boundary | Proposed fulfillment-service/it/it_read_only_access_test.go; follow public client and token setup in it_hub_secrets_test.go and it_tool.go | make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment from fulfillment-service/; requires Kind, dev profile, and Kafka test support | Fulfillment Service, PostgreSQL, Keycloak, and Kafka are real; tenant events are test fixtures | Proposed case in an existing runnable suite; Fulfillment Service [DEV] |
| TC-FR1-03 | Fulfillment Service: tenant Get/List scope for reader access | Component integration; deployed Clusters API through interceptor, handler, and PostgreSQL | Proposed fulfillment-service/it/it_read_only_access_test.go; follow public client pattern in it_hub_secrets_test.go | make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment from fulfillment-service/; requires Kind and the documented dev profile | Fulfillment Service, PostgreSQL, and Keycloak are real; tenants and clusters are test fixtures | Proposed case in an existing runnable suite; Fulfillment Service [DEV] |
| TC-FR1-04 | OSAC UI: both reader roles map to the reader session | Unit; role claim mapping in the login/session path | Proposed osac-ui/apps/app-frontend/src/hooks/oidc-login.test.tsx | pnpm test from osac-ui/; requires installed workspace dependencies | UI role-mapping code runs; token claims are fixtures; no API or cluster is used | Proposed test in an existing runnable UI suite; OSAC UI [DEV] |
| TC-FR1-05 | Fulfillment Service: cloud-provider-reader preserves provider scope | Component integration; deployed Clusters API through existing authorization checks | Proposed fulfillment-service/it/it_read_only_access_test.go | make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment from fulfillment-service/; requires Kind and the documented dev profile | Fulfillment Service, PostgreSQL, and Keycloak are real; provider scope and clusters are test fixtures | Proposed case in an existing runnable suite; Fulfillment Service [DEV] |
| TC-FR1-06 | Fulfillment Service: reader-only Create/Update/Delete denial through public gRPC interceptor | Component integration; public Clusters API authorization and persisted state | Proposed fulfillment-service/it/it_read_only_access_test.go; use `tool.makeKeycloakTokenSource`, `tool.makeGrpcConn`, and `publicv1.NewClustersClient` patterns from it_hub_secrets_test.go and it_tool.go; follow Cluster fixtures in it_public_clusters_test.go | make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment from fulfillment-service/; requires Kind, the documented dev profile, Keycloak test identity, and PostgreSQL | Fulfillment Service, PostgreSQL, and Keycloak are real; tenant and cluster fixtures are test data; no provider runs | Proposed case in an existing runnable suite; Fulfillment Service [DEV] |
| TC-FR2-01 | Fulfillment Service: RoleBinding sync and old/refreshed token calls for both roles | Component integration; RoleBindings API through reconciliation and public gRPC interceptor | Extend fulfillment-service/it/it_role_binding_reconciler_test.go; follow READY polling and cleanup patterns there, plus Keycloak token and public gRPC client setup in it_tool.go and it_hub_secrets_test.go; use the valid Cluster fixture from it_public_clusters_test.go and extend the token fixture to exercise its refresh-token grant | make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment from fulfillment-service/; requires Kind, dev profile, Keycloak test identities, and PostgreSQL | Fulfillment Service, PostgreSQL, and Keycloak are real; external providers are omitted | Existing runnable suite; Fulfillment Service [DEV] |
| TC-FR2-02 | OSAC UI: select either reader role and submit RoleBindings | Unit; React page/form with API fixtures | Proposed osac-ui/libs/ui-components/src/components/RoleBinding/CreatePage/RoleBindingCreatePage.test.tsx | pnpm test from osac-ui/; requires installed workspace dependencies | React components execute; APIs and identity/session are fixtures; no cluster is used | Proposed test in an existing runnable UI suite; OSAC UI [DEV] |
| TC-FR2-03 | OSAC UI and Fulfillment Service: assignment, refresh, scoped read, and hidden controls | E2E; browser-to-UI-to-Fulfillment-to-Keycloak journey | Proposed temporary spec under osac-ui/apps/playwright/scratch/; follow the existing Playwright session setup in osac-ui/apps/playwright/README.md; not committed or CI coverage | Start the reader session with `pnpm playwright:setup`, use a separate browser profile for the administrator session, then run the scratch spec with `pnpm playwright:run` from osac-ui/; requires OSAC_UI_BASE_URL, both test identities, and a deployed UI/service profile. | UI, Fulfillment Service, PostgreSQL, and Keycloak are real; no mock proves this boundary | Proposed manual acceptance path; no persisted regression coverage or QE Jira ticket exists. Owner: OSAC QE; create follow-up during decomposition |
| TC-FR2-04 | User documentation: API and UI reader instructions | Manual review of a documentation artifact; not a runtime test tier | Existing docs/guides/tenant-identity-and-access-guide.md | Review the rendered documentation change from the repository root; no automated docs command is defined for this content | Documentation is real; no runtime services are involved | Manual review is defined; Fulfillment Service [DEV] |

## Gaps

### Requirement Coverage Gaps

All PRD in-scope bullets have test cases. The testplan uses FR-1 and FR-2
only as draft trace references because the PRD has no numbered requirements.

### Interface Change Coverage Gaps

All four interface changes are exercised by at least one test case.

### Execution and Design Gaps

- TC-FR2-03 can be checked with the OSAC UI's manual Playwright harness, but
  scratch specs are not committed or run in CI. No persisted browser E2E test
  or follow-up Jira ticket exists yet. Create reusable [QE] coverage during
  decomposition; the manual run is not regression coverage.
- The reader-only fallback exception, additive explicit role grants, provider
  scope, UI controls, and token refresh behavior are defined in the design.
  The open regression gap is the lack of persisted browser E2E coverage.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 10 |
| Critical | 7 |
| High | 2 |
| Medium | 1 |
| Low | 0 |
| Automated | 8 |
| Manual | 2 |
| Requirements with test cases | 2 / 2 |
| Interface changes with test cases | 4 / 4 |

---

## Provenance

Authored: draft @ design 0.11.5 - 4164796, workspace main @ 95fbc127c
Final: respond @ design 0.11.5 - d1824b1, workspace main @ 95fbc127c

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"d1824b1","source_repo":"95fbc127c","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond","respond","respond","respond","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
