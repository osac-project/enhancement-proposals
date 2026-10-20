# Testplan — OSAC-6211

## Overview

- **Feature:** OSAC-6211 — Assign read-only API permissions to users
- **Total test cases:** 8
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

- The OPA policy test input identifies a user with the proposed reader role.

##### Steps

1. Enumerate registered public and private gRPC methods and evaluate each path
   for the reader identity.
2. Evaluate paths ending in GetByName, ListServices, and WatchSomething.
3. Evaluate methods under the metadata, health, and reflection prefixes.

##### Expected Results

- The OPA decision is allow for each registered method whose final path
  segment is exactly Get, List, or Watch.
- The OPA decision is deny for every registered method outside that exact set,
  including Signal, health, and reflection methods.
- Methods under metadata, health, and reflection prefixes use the exact-name
  rule; there is no blanket prefix allow for a reader.
- GetByName, ListServices, and WatchSomething are denied because none is an
  exact method name in the allowed set.

#### TC-FR1-02: Watch only streams events visible to the reader's tenant

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-1 | critical | automated | Component integration | Fulfillment Service [DEV] |

##### Preconditions

- A container runtime is available to start the Kafka test container.
- The EventsServer test has events for two tenants and a Watch subscriber
  scoped to one tenant.

##### Steps

1. Start a Watch stream with the test tenant scope.
2. Publish one event for that tenant and one event for the other tenant.
3. Collect events from the Watch stream.

##### Expected Results

- The stream contains the event for the reader's tenant.
- The stream contains no event belonging to the other tenant.

#### TC-FR1-03: Denied writes do not change stored objects

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-1 | critical | automated | Component integration | Fulfillment Service [DEV] |

##### Preconditions

- Fulfillment Service, PostgreSQL, and Keycloak are deployed using the
  documented fulfillment integration profile.
- Two tenant users and existing test objects are available; the reader token
  contains the reader role and one tenant claim.

##### Steps

1. As the reader, Get and List an object in the assigned tenant.
2. Check that the List response contains no known object IDs from the other
   tenant.
3. Attempt Create, Update, and Delete calls for a valid test object.
4. Read the affected database-backed objects again as an authorized test
   identity.

##### Expected Results

- Get returns the requested in-scope object, and List contains only objects
  visible in the reader's tenant.
- No known object ID from the other tenant appears in the List response.
- Each Create, Update, and Delete call returns gRPC
  PERMISSION_DENIED with message permission denied.
- The attempted Create leaves no row; Update leaves the stored fields
  unchanged; Delete leaves the object present.

#### TC-FR1-04: Map a reader token to the reader UI session role

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-3 | high | automated | Unit | OSAC UI [DEV] |

##### Preconditions

- The UI session test has a token claim containing the selected reader role
  and no other role that maps to an administrative session.

##### Steps

1. Pass the token's role claims through the session role mapper.
2. Inspect the resulting UI session role.

##### Expected Results

- The session role is reader.
- The role mapper does not classify the user as tenant-user or an
  administrator.

### FR-2: Authorized administrators can assign read-only access through the API and UI, and documentation explains it

#### TC-FR2-01: Assign a reader role through the API and sync it to Keycloak

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-2 | critical | automated | Component integration | Fulfillment Service [DEV] |

##### Preconditions

- The documented fulfillment integration profile has Fulfillment Service,
  PostgreSQL, and Keycloak running.
- An authorized administrator and a tenant user exist in the test tenant.

##### Steps

1. Create a RoleBinding for the test user through the existing RoleBindings
   API using the selected reader role.
2. Wait for RoleBinding status to become READY.
3. Obtain a new token for the assigned user and inspect its role claim.

##### Expected Results

- The API creates the RoleBinding and returns its resource identity.
- The RoleBinding status reaches READY.
- The new token contains the assigned reader role.
- A reader method call is allowed, and a write method call returns
  PERMISSION_DENIED.

#### TC-FR2-02: Assign a reader role in the Role Bindings UI

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-3 | high | automated | Unit | OSAC UI [DEV] |

##### Preconditions

- The UI test has an administrator session and API fixtures containing a
  reader role and an eligible user.

##### Steps

1. Open the Role Bindings page and start creating a binding.
2. Select the reader role and eligible user, then submit the form.

##### Expected Results

- The reader role appears by its configured title in the role selector.
- The submitted RoleBinding request contains the selected role and user.
- The UI displays the returned binding and its synchronization status.

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

1. Sign in as the administrator and assign the reader role in the UI.
2. Wait for the RoleBinding to show READY.
3. Re-run the browser login setup with the assigned user's credentials to
   obtain a new token.
4. Open an authorized object as the reader.

##### Expected Results

- The assignment reaches READY.
- The reader session displays the authorized object and no object outside its
  tenant scope.

#### TC-FR2-04: Check user-facing API and UI permission guidance

| Interface Change | Priority | Automation | Tier | Owner |
|-----------------|----------|------------|------|-------|
| IC-4 | medium | manual | Manual documentation review (not a runtime test tier) | Fulfillment Service [DEV] |

##### Preconditions

- The updated tenant identity and access guide is available in the change
  under review.

##### Steps

1. Read the guide's API and UI assignment instructions.
2. Check the documented method names, denial behavior, tenant scope, and
   RoleBinding synchronization status against the PRD and design.

##### Expected Results

- The guide names Get, List, and Watch as the only allowed method names for
  a reader.
- The guide says other methods are denied and that tenant/object scope still
  applies.
- The guide explains how to assign the role through both API and UI and how
  to recognize synchronization status.

## Test Execution Evidence

| Case | Owning component and behavior | Required tier and boundary | Suite or proposed location | Command, workdir, and prerequisites | Real and simulated dependencies | Execution readiness and owner |
|------|-------------------------------|----------------------------|---------------------------|-----------------------------------|-------------------------------|-------------------------------|
| TC-FR1-01 | Fulfillment Service: OPA method decision | Unit; policy evaluator with reader identity claims | Extend fulfillment-service/internal/auth/authorization_evaluator_test.go | ginkgo run -r internal from fulfillment-service/; no cluster required, but the recursive suite requires a container runtime | OPA runs in process; policy inputs and identities are test controlled. The documented command also runs other internal suites, including container-backed tests | Existing unit suite; Fulfillment Service [DEV] |
| TC-FR1-02 | Fulfillment Service: Watch tenant filtering | Component integration; EventsServer with Kafka boundary | Existing fulfillment-service/internal/servers/events_server_test.go | ginkgo run -r internal from fulfillment-service/; requires a working container runtime for the Kafka test container | EventsServer runs in process over bufconn; Kafka runs in a real test container; tenancy logic and events are test controlled | Existing runnable suite; Fulfillment Service [DEV] |
| TC-FR1-03 | Fulfillment Service: public API scope checks and no mutation on denied writes | Component integration; deployed API through interceptor, handler, and PostgreSQL | Proposed fulfillment-service/it/it_read_only_access_test.go; existing suite is it/ | make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment from fulfillment-service/; requires Kind and the documented dev profile | Fulfillment Service, PostgreSQL, and Keycloak are real; external providers are not part of this API-only case | Proposed case in an existing runnable suite; Fulfillment Service [DEV] |
| TC-FR1-04 | OSAC UI: reader token to session role mapping | Unit; role claim mapping in the login/session path | Proposed osac-ui/apps/app-frontend/src/hooks/oidc-login.test.tsx | pnpm test from osac-ui/; requires installed workspace dependencies | UI role-mapping code runs; token claims are fixtures; no API or cluster is used | Proposed test in an existing runnable UI suite; OSAC UI [DEV] |
| TC-FR2-01 | Fulfillment Service: RoleBinding persistence and Keycloak role sync | Component integration; RoleBindings API through reconciliation | Extend fulfillment-service/it/it_role_binding_reconciler_test.go | make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment from fulfillment-service/; requires Kind, dev profile, and test identities | Fulfillment Service, PostgreSQL, and Keycloak are real; external providers are omitted | Existing runnable suite; Fulfillment Service [DEV] |
| TC-FR2-02 | OSAC UI: role selection and RoleBinding submission | Unit; React page/form with API fixtures | Proposed osac-ui/libs/ui-components/src/components/RoleBinding/CreatePage/RoleBindingCreatePage.test.tsx | pnpm test from osac-ui/; requires installed workspace dependencies | React components execute; APIs and identity/session are fixtures; no cluster is used | Proposed test in an existing runnable UI suite; OSAC UI [DEV] |
| TC-FR2-03 | OSAC UI and Fulfillment Service: deployed assignment and reader object view | E2E; browser-to-UI-to-Fulfillment-to-Keycloak journey | Temporary spec under osac-ui/apps/playwright/scratch/; not committed or CI coverage | Run pnpm playwright:setup with admin credentials to assign, then rerun setup with reader credentials and pnpm playwright:run from osac-ui/; requires OSAC_UI_BASE_URL, OSAC_USERNAME, OSAC_PASSWORD, and a deployed UI/service profile | UI, Fulfillment Service, PostgreSQL, and Keycloak are real; no mock proves this boundary | Manual harness is available, but it is not persisted regression coverage. Owner: OSAC QE; no follow-up Jira ticket exists |
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
  or follow-up Jira ticket exists yet. Create and assign reusable [QE]
  coverage during decomposition; do not treat the manual run as regression
  coverage.
- The accepted reader role names, cloud-provider assignment scope, and UI
  mutation-control behavior remain open in §9 of the design. Finalize those
  choices before implementation tests lock expected values.
- TC-FR2-01 and TC-FR2-03 obtain a new token after the RoleBinding reaches
  READY. They do not establish whether existing tokens must lose write
  permissions immediately; that timing remains open in §9.4 of the design.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 8 |
| Critical | 5 |
| High | 2 |
| Medium | 1 |
| Low | 0 |
| Automated | 6 |
| Manual | 2 |
| Requirements with test cases | 2 / 2 |
| Interface changes with test cases | 4 / 4 |
