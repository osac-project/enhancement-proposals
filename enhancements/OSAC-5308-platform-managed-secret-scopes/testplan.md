# Testplan — OSAC-5308

## Overview

- **Feature** — Platform-managed Secret scopes for Core in 0.6. [PRD](prd.md), [Design](design.md).
- **Total test cases** — 21, including the seven rows in the Secret type table.
- **Requirements covered** — 5 of 5 behavioral PRD requirements. IDs match the [clarification log](clarifications.md). Documentation is tracked in Gaps.
- **Interface changes covered** — 7 of 7. These are planned tests.

## Test Case Index

| ID | Scenario | IC | Priority |
| --- | --- | --- | --- |
| TC-R1Q1-01 | Manage each supported Secret type | IC-1 | critical |
| TC-R1Q1-02 | Keep scope and ownership immutable | IC-1 | high |
| TC-R1Q1-03 | Preserve the three existing scopes | IC-1 | high |
| TC-R1Q2-01 | Delegate controller CRUD and bind Get to the owner | IC-1, IC-2 | critical |
| TC-R1Q2-02 | Resolve a protected storage Secret by name | IC-2 | critical |
| TC-R1Q3-01 | Hide protected metadata and values from tenants | IC-1 | critical |
| TC-R1Q3-02 | Suppress protected Secret watch events | IC-3 | high |
| TC-R1Q3-03 | Redact references and preserve them on update | IC-3 | critical |
| TC-R1Q3-04 | Limit Vault data and metadata access | IC-7 | critical |
| TC-R1Q4-01 | Delete one tenant's protected Secrets and Vault entries | IC-4, IC-7 | critical |
| TC-R1Q4-02 | Keep offboarding pending when Vault deletion fails | IC-4, IC-7 | critical |
| TC-R1Q4-03 | Serialize a protected write with tenant deletion | IC-4 | high |
| TC-R1Q5-01 | Manage protected Secrets through the private REST API | IC-1 | high |
| TC-R1Q5-02 | Manage protected Secrets through the CLI | IC-5 | high |
| TC-R1Q5-03 | Manage protected Secrets through the web console | IC-6 | critical |

## Test Cases

### R1.Q1 — Four scopes and existing type policy

#### TC-R1Q1-01 — Manage each supported Secret type

| Interface Change | Priority | Automation |
| --- | --- | --- |
| IC-1 | critical | automated |

##### Steps

1. As a provider admin, use private Create and Get for each type with the fixture below and `platform_managed=true` on tenant A.
2. Attempt to change `data` using an explicit field mask. Read the object again, then delete it.

##### Expected Results

Every Create returns `platform_managed=true` and owner A. Get returns the submitted bytes. After Delete, Get by ID returns `NotFound`.

| Type | Data fixture | Update result |
| --- | --- | --- |
| Opaque | `fixture=first` | Get returns `fixture=second`. |
| Pull secret | `.dockerconfigjson` with synthetic registry credential JSON | Get returns the replacement bytes. |
| Kubeconfig | `kubeconfig` with a synthetic kubeconfig | Get returns the replacement bytes. |
| User data | `userdata` with a cloud-init fixture | Update returns `InvalidArgument`. Get returns the original bytes. |
| Value | `value=first` | Get returns `value=second`. |
| SSH public key | `public_key` with a generated test public key | Get returns the replacement public key. |
| Service-account credential | `client_secret` with a synthetic value | Provider-admin Get returns the replacement bytes. |

#### TC-R1Q1-02 — Keep scope and ownership immutable

| Interface Change | Priority | Automation |
| --- | --- | --- |
| IC-1 | high | automated |

##### Steps

1. As a provider admin, attempt protected Create without an owner, with `shared` or `system` as owner, and with the hub backend.
2. Attempt to clear an existing protected Secret's flag or move it to another tenant. Attempt to create a second protected Secret at the same owner, project, and name.

##### Expected Results

- Invalid scope, backend, and update requests return `InvalidArgument`. The duplicate returns `AlreadyExists`.
- A subsequent admin Get returns the original ID, scope, and owner.

#### TC-R1Q1-03 — Preserve the three existing scopes

| Interface Change | Priority | Automation |
| --- | --- | --- |
| IC-1 | high | automated |

##### Steps

1. Use a pre-feature client and records restored from before the migration. Also create Secrets with the new flag omitted under tenant A, `shared`, and `system`.
2. Query them through the public API as a tenant and as a provider admin. As the Fulfillment controller, call private Get with just the Secret ID for each existing scope. Verify that a shared template can select its existing shared pull Secret.

##### Expected Results

- The tenant can list and Get its ordinary Secret. Shared metadata follows the existing visibility rules, and direct tenant Get of shared values returns `PermissionDenied`.
- Provider-admin public List includes the global `system` Secret and public Get returns its fixture value. Tenant Get returns `NotFound`.
- The controller's ID-only private Gets return the fixture values for the existing scopes. The configured template selects its shared pull Secret.

### R1.Q2 — Controller access and tenant-bound resolution

#### TC-R1Q2-01 — Delegate controller CRUD and bind Get to the owner

| Interface Change | Priority | Automation |
| --- | --- | --- |
| IC-1, IC-2 | critical | automated |

##### Preconditions

- A disposable deployment with the provisioned Fulfillment controller client and a managed tenant automation identity. Tenants A and B have distinct test Secrets.

##### Steps

1. Use a token issued to the Fulfillment controller to create a protected Secret for A, list by owner, Get with `expected_tenant=A`, update it, and Get again.
2. Repeat Get for the same ID with `expected_tenant=B`, then without `expected_tenant`. Also submit the private Get as managed tenant automation and as a platform service identity with no Secrets grant.
3. Delete A's Secret as the controller and read B's Secret.

##### Expected Results

- Owner A's private list includes the Secret and omits its values. The matched reads give the original and replacement bytes.
- The wrong owner returns `NotFound`. The missing expected owner returns `InvalidArgument`. Tenant automation and the ungranted platform service receive `PermissionDenied` from the private API.
- Get of the deleted ID returns `NotFound`. Get for B still returns B's original bytes.

#### TC-R1Q2-02 — Resolve a protected storage Secret by name

| Interface Change | Priority | Automation |
| --- | --- | --- |
| IC-2 | critical | automated |

##### Preconditions

- Tenants A and B each own a protected opaque Secret named `vast-east` in their `storage` project with distinct synthetic `config.yaml` values. A also has an ordinary Secret with the same name and project.

##### Steps

1. As the authorized Fulfillment controller, use private `Secrets/List` with exact owner, project `storage`, name `vast-east`, and `platform_managed=true` for each tenant. Get each returned ID with its matching `expected_tenant`.
2. Repeat the name lookup for an empty project scope in A.

##### Expected Results

- Each List returns one ID and no value. Each Get returns only the selected tenant's synthetic `config.yaml` value. A's ordinary Secret does not appear.
- The empty project returns zero matches.

### R1.Q3 — Protected values, metadata, and reference redaction

#### TC-R1Q3-01 — Hide protected metadata and values from tenants

| Interface Change | Priority | Automation |
| --- | --- | --- |
| IC-1 | critical | automated |

##### Steps

1. Create a tenant-associated protected Secret in A and a global protected Secret. Query public List with a name filter, `limit=0`, and a positive page size as A's Tenant Admin and Tenant User, a tenant automation identity, and a user from B.
2. For supported public verbs, try each protected ID and a random absent ID. Try calling the private endpoint with the same tenant credentials.
3. As A's authorized tenant user, create an ordinary Secret with the same name and project as A's protected one. Repeat List and Get.
4. As provider admin, create a tenant-managed and a platform-managed service-account credential Secret for A. As A's Tenant Admin, filter public List for both and Get each by ID.

##### Expected Results

- Before the ordinary create, filtered List returns `total=0` and an empty page. No protected name or ID appears.
- Public Get, Update, and Delete return the same `NotFound` result as for the random absent ID when the caller has that verb. Private RPCs return `PermissionDenied`.
- The ordinary create succeeds. An authorized List returns exactly one result and Get returns only the ordinary values.
- A's Tenant Admin sees only the tenant-managed credential in List and can Get its fixture value. Get for the platform-managed credential returns `NotFound`.

#### TC-R1Q3-02 — Suppress protected Secret watch events

| Interface Change | Priority | Automation |
| --- | --- | --- |
| IC-3 | high | automated |

**Steps:** 1. Open an authenticated public watch as A before the writes. → 2. Create, update, and delete protected Secrets in A and `system`, then perform the same operations on a visible Secret to provide control events.

**Expected:** Within 30 seconds of the final visible operation, the watch has delivered the visible controls in broker order and contains no protected Secret payload or identifier. Use the watched partition's control events to distinguish filtering from an inactive subscriber.

#### TC-R1Q3-03 — Redact references and preserve them on update

| Interface Change | Priority | Automation |
| --- | --- | --- |
| IC-3 | critical | automated |

##### Preconditions

- Seed a tenant-readable resource with a protected reference in the Fulfillment server test fixture. Include a second resource without a reference and a Secret whose name exists only in the protected scope. Mapper fixtures include full and local reference forms for both protected scopes.

##### Steps

1. Get and list the resource as A's Tenant Admin. Filter the list by the configured Secret ID and pass a fixture event through public projection.
2. Submit an allowed label update that includes the redacted reference. On the second resource, try to attach the protected Secret by name or ID through a public write.
3. Check the stored reference via private Get as the provider admin. Use an eligible private writer to update it by name with a same-tenant Secret of the expected type and lifecycle state. Try a wrong owner, wrong type, invalid lifecycle state, and an ungranted writer. Exercise a permitted credential destination update and the same attempted update without the grant.
4. Fail the metadata lookup when projecting public output for the referenced resource.

##### Expected Results

- The public reference message stays present with empty identifying fields for both protected scopes. The ID filter returns zero items and a zero total. The event contains no Secret ID, name, scope, owner, project, or bytes.
- The metadata update persists the new label. The protected-only name and ID have the same rejection as a missing name or ID.
- After the public metadata update, the provider-admin Get still returns the original canonical reference.
- The permitted private write stores the new canonical name and ID. Denied writes preserve the stored reference and credential destination. Only an authorized platform writer can change the destination.
- When the metadata lookup fails, the affected public output is withheld.

#### TC-R1Q3-04 — Limit Vault data and metadata access

| Interface Change | Priority | Automation |
| --- | --- | --- |
| IC-7 | critical | automated |

**Steps:** 1. Store a protected Secret through Fulfillment. → 2. Read its data and list A's protected keys against the real backend with the Fulfillment role and a role restricted to A's ordinary mount.

**Expected:** The Fulfillment role reads the fixture value and lists the expected key. The restricted role's read and list receive HTTP `403` without key names or values. Its ordinary mount remains readable according to that role's policy.

### R1.Q4 — Offboarding deletes owned protected Secrets

#### TC-R1Q4-01 — Delete one tenant's protected Secrets and Vault entries

| Interface Change | Priority | Automation |
| --- | --- | --- |
| IC-4, IC-7 | critical | automated |

##### Preconditions

- Tenants A and B have protected Secrets with the same name. A has a protected Secret in the root project and one in a child project. Seed one synthetic unreferenced key in A's protected Vault storage to represent an interrupted Create.

##### Steps

1. Request deletion of A via the private Tenant API. Poll every second for up to five minutes until the tenant Get returns `NotFound`.
2. Check A's owner filter and verify cleanup through the Vault API for the chosen layout. Read B's Secret and a platform-global control Secret.

##### Expected Results

- The controller removes A's project Secrets. The provider-admin owner filter returns `total=0` when tenant deletion finishes.
- A's Vault namespace is gone for tenant-local placement. For shared placement, the mount is available and lists zero keys under A's prefix. Both checks include the synthetic orphan. B and the global control return their original values.

#### TC-R1Q4-02 — Keep offboarding pending when Vault deletion fails

| Interface Change | Priority | Automation |
| --- | --- | --- |
| IC-4, IC-7 | critical | automated |

##### Steps

1. On an isolated backend, temporarily deny the Vault cleanup operation for the chosen layout, then request tenant deletion.
2. Observe the backend denial for A. Check tenant Get every second for 15 seconds following that denial. Restore the grant and allow the actual reconciler to retry.

##### Expected Results

- While the backend denies cleanup, tenant Get retains its deletion timestamp and still returns the tenant. The test observes a real deletion attempt and leaves completion to the controller.
- Within five minutes of restoring the grant, tenant Get returns `NotFound` and Vault confirms A's protected data is gone using the check from TC-R1Q4-01. Fixture teardown restores the policy even if the test fails.

#### TC-R1Q4-03 — Serialize a protected write with tenant deletion

| Interface Change | Priority | Automation |
| --- | --- | --- |
| IC-4 | high | automated |

##### Steps

1. Use concurrent API clients and a test barrier to exercise both lock orders for protected Create and tenant Delete.
2. Read the caller's result and wait for tenant deletion, using the lifecycle bound from TC-R1Q4-01 for the deployed check.

##### Expected Results

- When deletion takes the owner lock first, Create returns `FailedPrecondition`. When Create finishes first, its returned ID becomes `NotFound` before tenant removal completes.
- Both lock orders end with A's protected Vault storage removed, using the check from TC-R1Q4-01. The deployed case uses the real storage path and controller. The in-process PostgreSQL subcase makes the ordering deterministic.
- Add the timed-out-write subcase after Core resolves the settlement mechanism. Tenant deletion completes only after cleanup is verified and the timed-out operation can no longer add protected data for A.

### R1.Q5 — Provider-admin workflows through three interfaces

#### TC-R1Q5-01 — Manage protected Secrets through the private REST API

| Interface Change | Priority | Automation |
| --- | --- | --- |
| IC-1 | high | automated |

##### Steps

1. As a provider admin, POST a protected `VALUE` Secret under A and B. GET the private collection with the owner and flag CEL filter for A.
2. PATCH A's data with an explicit mask, GET by ID, then DELETE A's Secret and query both owners again.

##### Expected Results

- The filter for A returns only A's ID and no Secret data. Get by ID returns the replacement value.
- After deleting A's Secret, the filter for A returns zero and B's still returns one. Get of A's ID returns HTTP `404`.

#### TC-R1Q5-02 — Manage protected Secrets through the CLI

| Interface Change | Priority | Automation |
| --- | --- | --- |
| IC-5 | high | automated |

##### Steps

1. In a private admin session, run `osac --tenant acme create secret --platform-managed --name fixture --type value --from-file=value=<fixture-file>` and capture its ID. Use `get secret --filter` for scope and owner, `describe secret <id>`, and `get secret <id> -o yaml`.
2. Use `edit secret <id>` to update the data, verify it with structured Get, and delete by ID. Repeat Get from a tenant session while a second protected test Secret exists.

##### Expected Results

- List and describe identify the owner and scope. Structured Get in the private session returns the expected synthetic bytes before and after the edit. Private Delete exits zero and the following Get reports `NotFound`.
- The tenant session's Get of an existing protected ID reports `NotFound`, and its output contains no protected metadata or data.

#### TC-R1Q5-03 — Manage protected Secrets through the web console

| Interface Change | Priority | Automation |
| --- | --- | --- |
| IC-6 | critical | automated |

##### Steps

1. In the deployed console as provider admin, choose **Platform-managed**, select tenant A, create a Secret, then filter by A. Open the details, update its fixture value, and read the result.
2. Sign in as A's Tenant Admin, open the tenant Secrets page, and try the captured detail link.
3. Return as provider admin, delete the Secret, and check the owner-filtered list. In the UI unit subcase, render a resource with an empty reference through the mocked Connect transport.

##### Expected Results

- The admin list and detail show the owner and scope. The edited value appears through the allowed detail action.
- The tenant list omits the Secret, and its detail link displays the ordinary unavailable-resource state. The rendered empty reference shows **Configured** with no Secret link or identifier.
- The admin list no longer includes the deleted Secret.

## Execution and Boundaries

Paths below are relative to the `osac` repository. The cases extend the named suites. The commands are suite entry points. [Test policy](https://github.com/osac-project/osac/blob/6c883aa9f/docs/INTEGRATION-TESTING.md).

| Suite | Command and prerequisites | Real dependencies and doubles |
| --- | --- | --- |
| A — Fulfillment server and mapper | In `fulfillment-service/`, `ginkgo run --timeout 10m internal/servers`. Extend `private_secrets_server_test.go`, `generic_mapper_test.go`, and `events_server_test.go`. Container runtime for PostgreSQL. | Component integration for handler/DB cases uses an in-process Fulfillment server and real PostgreSQL, with controlled tenancy and Vault. Mapper-only cases use the unit tier with a lookup double. |
| B — Fulfillment `it/` | From the monorepo root, `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`, after `make -C osac-installer install-infra PLATFORM=kind PROFILE=dev NS=osac`. Use a disposable Kind cluster with the service-only phase and the existing credentials fixtures. | Real Fulfillment, PostgreSQL, Keycloak, OpenBao, and deployed Fulfillment reconcilers. Watch tests use real Kafka. The name lookup uses synthetic bundle values. The operator, AAP, and external providers are outside this boundary. |
| C — Vault policy and failure harness | Extend Suite B with a **proposed** fixture for the restricted ordinary-mount role, owner cleanup checks, and a reversible failure for the chosen Vault layout. The target is Suite B after that fixture is added. | Real OpenBao, Vault data and metadata APIs, and Fulfillment credentials. A test-controlled policy change injects the failure. |
| D — Maintained UI browser suite | In `osac-ui/`, use the Playwright harness in `apps/playwright` and proposed `apps/e2e-tests/src/generic/secret-scopes.spec.ts`. Register a `secret-scopes` project, then use the proposed command `pnpm --filter @osac/playwright exec playwright test --project=secret-scopes --workers=1`. Requires a deployed console with provider-admin and tenant-admin browser identities. | E2E through a real browser, SPA, Go proxy, Keycloak, Fulfillment, PostgreSQL, and OpenBao. Isolate the fixture's tenants and delete its test-owned objects in teardown. |
| E — Console reference display | In `osac-ui/`, `pnpm --filter @osac/app-frontend run test`. Extend the shared resource-detail tests. | Unit coverage measures rendering with a mocked Connect transport. |

| Owner | Behavior and requirement | Tier and evidence path |
| --- | --- | --- |
| Fulfillment [DEV] | Secret type policy and old-client inputs, IC-1, R1.Q1 | Component integration. TC-R1Q1-01–03 in B, extending `it_public_secrets_test.go`. Compatibility uses a pre-feature client and a fixture with pre-migration Secrets. |
| Fulfillment [DEV] | Ownership locks and CRUD permissions, IC-1/2/4, R1.Q2 and R1.Q4 | Component integration. TC-R1Q2-01 and TC-R1Q4-03 in A and B, extending `private_secrets_server_test.go` and `it_tenant_lifecycle_test.go`. The deterministic lock-order barrier lives in A. |
| Fulfillment [DEV] | Name-based lookup and controller Get, IC-2, R1.Q2 | Component integration. TC-R1Q2-02 in B, extending `it_public_secrets_test.go` with an authorized controller client and synthetic opaque bundles. |
| Fulfillment [DEV] | Public output and private reference updates, IC-3, R1.Q2–Q3 | Component integration and unit. TC-R1Q3-03 in A with a proposed protected-reference fixture, real PostgreSQL, and a synthetic event passed to the public event handler. The mapper suite covers full and local references and a failed metadata lookup. The resource fixture covers reference authorization, owner, type, lifecycle, and destination changes. |
| Fulfillment [DEV] | Public List/Get and watch visibility, IC-1/3, R1.Q3 | Component integration. TC-R1Q3-01–02 in B, extending `it_public_secrets_test.go` and a proposed `it_protected_secret_events_test.go`. Real broker controls establish delivery. |
| Fulfillment and installer [DEV] | Protected mount data access and owner cleanup, IC-4/7, R1.Q3 and R1.Q4 | Component integration. TC-R1Q3-04 and TC-R1Q4-01–02 in C, extending `it_tenant_lifecycle_test.go` and a proposed `it_protected_vault_policy_test.go`. The real policy-failure and orphan fixtures are new. |
| Fulfillment CLI and API [DEV] | Private REST and CLI management and tenant CLI denial, IC-1/5, R1.Q3 and R1.Q5 | Component integration. TC-R1Q5-01–02 in B, extending the Secret suite and CLI harness. Real authenticated private and public gateways, CLI, and store. |
| Web console [QE] | Provider and tenant browser journeys, IC-6, R1.Q5 | E2E. TC-R1Q5-03 in D. The existing browser harness supplies authentication. The Secret project and spec are proposed. |
| Web console [DEV] | Render redacted reference, IC-6, R1.Q5 | Unit subcase of TC-R1Q5-03 in E. |

## Gaps

### Requirement Coverage Gaps

- All five behavioral requirements have planned cases. Publishing the four-scope permission matrix and admin instructions is documentation work and has a release criterion in the design.
- The protected-reference fixture, OpenBao ACL failure fixture, and Secret browser project are pending implementation. Core and UI own the relevant work under the feature. Follow-up task IDs are unresolved. [OSAC-5308](https://redhat.atlassian.net/browse/OSAC-5308)
- Core owns the open Vault placement and timed-out write questions. The chosen layout determines the cleanup probe and fault injection in Suite C. TC-R1Q4-01 covers an orphan already present when cleanup starts. A write that lands after cleanup verification needs a case once the design resolves that behavior. [OSAC-5308](https://redhat.atlassian.net/browse/OSAC-5308)
- A deployed browser check for **Configured** needs a resource fixture with a protected reference. The identified CaaS storage consumer is follow-up work. TC-R1Q3-03 covers server projection and the TC-R1Q5-03 unit subcase covers console display until an eligible fixture is available. [OSAC-5308](https://redhat.atlassian.net/browse/OSAC-5308)

### Interface Change Coverage Gaps

- All seven interface changes have planned cases. IC-7's injected Vault failure and IC-6's browser flow depend on the proposed harness additions above.

## Summary

| Metric | Count |
| --- | --- |
| Total test cases | 21 |
| Critical | 15 |
| High | 6 |
| Medium | 0 |
| Low | 0 |
| Automated | 21 |
| Manual | 0 |
| Requirements with test cases | 5 / 5 behavioral |
| Interface changes with test cases | 7 / 7 |
