# Testplan — OSAC-6211

## Overview

- **Feature:** OSAC-6211 — Assign read-only API permissions to users
- **Total test cases:** 9
- **Requirements covered:** 2 of 2 draft trace references
- **Interface changes covered:** 4 of 4

The PRD has no requirement IDs. FR-1 maps to its first In Scope bullet; FR-2
maps to its second. These labels exist only to trace this testplan to the PRD.

## Test Cases

### FR-1: Readers can call Get, List, and Watch within existing access scope; other methods are denied

#### TC-FR1-01: Apply the exact gRPC method rule

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-1 | critical | automated | Unit | Fulfillment Service [DEV] |

##### Preconditions

- The OPA policy test inputs include `tenant-reader` and
  `cloud-provider-reader` identities, each alone and with an additional grant
  that allows `/osac.public.v1.Clusters/Create`,
  `/osac.public.v1.Clusters/Update`, and
  `/osac.public.v1.Clusters/Delete`, plus a non-reader client identity with
  the existing Create grant.
- The reviewed reader path list includes at least
  `/osac.public.v1.Clusters/Get`,
  `/osac.public.v1.Clusters/List`, and
  `/osac.public.v1.Events/Watch`.

##### Steps

1. Enumerate registered public and private gRPC methods and evaluate each
   method path for both reader roles.
2. Evaluate `/osac.public.v1.Clusters/Create`,
   `/osac.public.v1.Clusters/Update`, and
   `/osac.public.v1.Clusters/Delete` for each reader role, alone and with
   the broader grant.
3. Evaluate the same Create path for the non-reader client identity.
4. Evaluate method names `GetByName`, `ListServices`, and `WatchSomething`,
   plus health and reflection paths.

##### Expected Results

- The OPA decision allows every path in the reviewed reader list, including
  the three listed examples, and denies every registered path not in that list.
- Every reader-list entry ends in exactly `Get`, `List`, or `Watch`; all
  other registered methods are denied, including Signal, health, and
  reflection methods.
- Both reader roles enforce the same method restriction.
- Methods under metadata, health, and reflection prefixes use the exact-name
  rule; there is no blanket prefix allow for a reader.
- GetByName, ListServices, and WatchSomething are denied because none is an
  exact method name in the allowed set.
- The reader plus broader-grant identity is denied Create, Update, and Delete.
- The non-reader identity retains its existing grant for
  `/osac.public.v1.Clusters/Create`.

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

#### TC-FR1-03: Denied writes do not change stored objects

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
3. Attempt `/osac.public.v1.Clusters/Create`,
   `/osac.public.v1.Clusters/Update`, and
   `/osac.public.v1.Clusters/Delete` for a valid test object.
4. Read the affected database-backed objects again as an authorized test
   identity.

##### Expected Results

- Get returns `cluster-tenant-a`, and List contains only objects visible in
  `tenant-a`.
- Get for `cluster-tenant-b` returns `NOT_FOUND`, as required by the
  existing tenant-filtered Get contract.
- No object from `tenant-b` appears in the List response.
- Each Create, Update, and Delete call returns gRPC
  PERMISSION_DENIED with message permission denied.
- The attempted Create leaves no row; Update leaves the stored fields
  unchanged; Delete leaves the object present.

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
- Get for `cluster-provider-out-of-scope` returns the existing out-of-scope
  response.
- List contains only clusters in the user's existing provider scope; the
  reader role adds no tenant or provider visibility.

### FR-2: Authorized administrators can assign read-only access through the API and UI, and documentation explains it

#### TC-FR2-01: Assign a reader role through the API and sync it to Keycloak

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-2 | critical | automated | Component integration | Fulfillment Service [DEV] |

##### Preconditions

- The documented fulfillment integration profile has Fulfillment Service,
  PostgreSQL, and Keycloak running.
- An authorized administrator and test users for `tenant-reader` and
  `cloud-provider-reader` exist.
- Before the RoleBinding is created, each test user has the existing
  `general-client` role. Its policy allows
  `/osac.public.v1.Clusters/Create` and
  `/osac.public.v1.Clusters/Get`.
- Each test user can obtain a token before and after its RoleBinding changes.

##### Steps

1. Obtain a token for each test user and confirm its existing Create and Get
   decisions are allow.
2. Create a RoleBinding through the existing API for each seeded role:
   `tenant-reader` and `cloud-provider-reader`.
3. Wait for each RoleBinding status to become READY.
4. Inspect the old token's role claims and evaluate
   `/osac.public.v1.Clusters/Create` and
   `/osac.public.v1.Clusters/Get` with those claims.
5. Refresh or re-authenticate, inspect the new token's role claim, and evaluate
   `/osac.public.v1.Clusters/Get` for an in-scope cluster and
   `/osac.public.v1.Clusters/Create`.

##### Expected Results

- The API creates both RoleBindings and returns their resource identities.
- Each RoleBinding reaches READY after Keycloak synchronization.
- Each new token contains its assigned reader role.
- The old token keeps its original claims, and its existing Create and Get
  decisions stay allowed after READY; READY does not invalidate active tokens.
- The refreshed token can Get an in-scope cluster, while its Create decision
  is `PERMISSION_DENIED` because the reader role denies mutations.

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
- An administrator and a tenant user can log in, and the tenant has a
  resource the user may read.
- The manual browser harness has OSAC_UI_BASE_URL, OSAC_USERNAME, and
  OSAC_PASSWORD set for the current test identity.

##### Steps

1. Sign in as the administrator and assign `tenant-reader` in the UI.
2. Wait for the RoleBinding to show READY.
3. Re-run the browser login setup with the assigned user's credentials to
   obtain a new token.
4. Open an authorized object as the reader.
5. Check the reader's navigation and object actions for Create, Update, and
   Delete controls.

##### Expected Results

- The assignment reaches READY.
- The reader session displays the authorized object and no object outside its
  tenant scope.
- The UI hides Create, Update, and Delete controls for the reader.
- Server-side authorization still rejects direct mutation requests.
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

- The section names `tenant-reader` and `cloud-provider-reader`, and says
  only reviewed `Get`, `List`, or `Watch` methods are allowed.
- The section says all other methods are denied and existing tenant and
  provider scope still applies.
- The section explains API and UI assignment, hidden mutation controls, and
  that READY means Keycloak sync; users refresh or sign in again to update
  token claims.

## Graduation Criteria

- Policy unit tests enumerate registered gRPC methods. For reader identities,
  only reviewed paths ending in exactly `Get`, `List`, or `Watch` are
  allowed; all other methods are denied, including when another grant would
  allow a write. Non-reader behavior remains unchanged.
- Component integration tests verify tenant and provider scope, Watch filtering
  through the public gRPC interceptor, out-of-scope Get behavior, and no
  database changes after denied writes.
- RoleBinding tests verify both seeded roles, READY after Keycloak sync, and
  the old-token/new-token behavior around refresh.
- UI tests map both reader roles to the reader session; UI acceptance confirms
  mutation controls are hidden.
- User documentation covers the roles, method rule, existing scope, refresh
  timing, and UI behavior.
- Before release, OSAC QE either adds persisted E2E regression coverage or
  records an explicit acceptance of the manual-only gap.

## Test Execution Evidence

| Case | Owning component and behavior | Required tier and boundary | Suite or proposed location | Command, workdir, and prerequisites | Real and simulated dependencies | Execution readiness and owner |
|------|-------------------------------|----------------------------|---------------------------|-----------------------------------|-------------------------------|-------------------------------|
| TC-FR1-01 | Fulfillment Service: OPA reader precedence and method decision | Unit; policy evaluator with reader, mixed-role, and non-reader inputs | Extend fulfillment-service/internal/auth/authorization_evaluator_test.go | ginkgo run -r internal from fulfillment-service/; no cluster required, but the recursive suite requires a container runtime | OPA runs in process; method paths and identity claims are test controlled | Existing unit suite; Fulfillment Service [DEV] |
| TC-FR1-02 | Fulfillment Service: reader Watch authorization and tenant filtering | Component integration; public Events/Watch call through interceptor and Kafka boundary | Proposed fulfillment-service/it/it_read_only_access_test.go | make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment from fulfillment-service/; requires Kind, dev profile, and Kafka test support | Fulfillment Service, PostgreSQL, Keycloak, and Kafka are real; tenant events are test fixtures | Proposed case in an existing runnable suite; Fulfillment Service [DEV] |
| TC-FR1-03 | Fulfillment Service: tenant Get/List scope and denied writes | Component integration; deployed Clusters API through interceptor, handler, and PostgreSQL | Proposed fulfillment-service/it/it_read_only_access_test.go | make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment from fulfillment-service/; requires Kind and the documented dev profile | Fulfillment Service, PostgreSQL, and Keycloak are real; tenants and clusters are test fixtures | Proposed case in an existing runnable suite; Fulfillment Service [DEV] |
| TC-FR1-04 | OSAC UI: both reader roles map to the reader session | Unit; role claim mapping in the login/session path | Proposed osac-ui/apps/app-frontend/src/hooks/oidc-login.test.tsx | pnpm test from osac-ui/; requires installed workspace dependencies | UI role-mapping code runs; token claims are fixtures; no API or cluster is used | Proposed test in an existing runnable UI suite; OSAC UI [DEV] |
| TC-FR1-05 | Fulfillment Service: cloud-provider-reader preserves provider scope | Component integration; deployed Clusters API through existing authorization checks | Proposed fulfillment-service/it/it_read_only_access_test.go | make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment from fulfillment-service/; requires Kind and the documented dev profile | Fulfillment Service, PostgreSQL, and Keycloak are real; provider scope and clusters are test fixtures | Proposed case in an existing runnable suite; Fulfillment Service [DEV] |
| TC-FR2-01 | Fulfillment Service: RoleBinding sync and token refresh behavior for both roles | Component integration; RoleBindings API through reconciliation and token claims | Extend fulfillment-service/it/it_role_binding_reconciler_test.go | make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment from fulfillment-service/; requires Kind, dev profile, and test identities | Fulfillment Service, PostgreSQL, and Keycloak are real; external providers are omitted | Existing runnable suite; Fulfillment Service [DEV] |
| TC-FR2-02 | OSAC UI: select either reader role and submit RoleBindings | Unit; React page/form with API fixtures | Proposed osac-ui/libs/ui-components/src/components/RoleBinding/CreatePage/RoleBindingCreatePage.test.tsx | pnpm test from osac-ui/; requires installed workspace dependencies | React components execute; APIs and identity/session are fixtures; no cluster is used | Proposed test in an existing runnable UI suite; OSAC UI [DEV] |
| TC-FR2-03 | OSAC UI and Fulfillment Service: assignment, refresh, read, and hidden controls | E2E; browser-to-UI-to-Fulfillment-to-Keycloak journey | Temporary spec under osac-ui/apps/playwright/scratch/; not committed or CI coverage | Run pnpm playwright:setup with admin credentials to assign, then rerun setup with reader credentials and pnpm playwright:run from osac-ui/; requires OSAC_UI_BASE_URL, OSAC_USERNAME, OSAC_PASSWORD, and a deployed UI/service profile | UI, Fulfillment Service, PostgreSQL, and Keycloak are real; no mock proves this boundary | Manual acceptance only; no persisted regression coverage or QE Jira ticket exists. Owner: OSAC QE; create follow-up during decomposition |
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
- Role names, provider scope, UI controls, and token refresh behavior are
  defined in the design. The open regression gap is the lack of persisted
  browser E2E coverage.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 9 |
| Critical | 6 |
| High | 2 |
| Medium | 1 |
| Low | 0 |
| Automated | 7 |
| Manual | 2 |
| Requirements with test cases | 2 / 2 |
| Interface changes with test cases | 4 / 4 |
