# Testplan — OSAC-3976

## Overview

- **Feature:** OSAC-3976 — Tenant On-Boarded Status for Minimal Onboarding Requirements
- **Total test cases:** 19
- **Requirements with test cases:** 4 of 4 (real Secret Storage coverage is planned in TC-FR1-05)
- **Interface changes with test cases:** 5 of 5 (including proposed deployed browser coverage in TC-FR3-05)

The revised working PRD has no FR/NFR identifiers. FR-1 through FR-4 are local
traceability aliases for its four In Scope bullets; no standalone NFRs are
specified. All cases below are **planned, not run** for this design; no
implementation-test pass is claimed. Remaining TC IDs are stable after
removing the retired TC-FR2-02, so its numbering gap is intentional.

Role fixtures map Cloud Provider Admin to `cloud-provider-admin`, Tenant Admin
to `tenant-admin`, and Tenant User to `tenant-user`, as specified in PRD D16.
No additional role is introduced.

## Planning coverage matrix

Every row below inherits its execution command, working directory, prerequisites,
real-versus-controlled dependency disclosure, and follow-up status from the
named cases' Coverage Evidence blocks. All rows are planned and not run.
Owning work is `[DEV]` for component behavior and `[QE]` for deployed journeys;
no individual Tasks have been decomposed or assigned. The source guidance is
`docs/INTEGRATION-TESTING.md` and the affected component `AGENTS.md` files in
OSAC source revision `0d54f8b27`.

| Component / behavior | Requirements / interfaces | Tier / work owner | Cases / required boundary |
|---|---|---|---|
| Fulfillment aggregation, evidence mapping, recovery | FR-1, FR-4 / IC-1, IC-2 | Unit / DEV OSAC-Core | TC-FR1-01–04, TC-FR1-06–07; pure projector and synthetic conditions, no provider claims |
| Fulfillment Vault/Breakglass evidence persistence | FR-1, FR-4 / IC-1, IC-2 | Component integration / DEV OSAC-Core | TC-FR1-05; real reconciler, Vault, Keycloak, Secrets API and PostgreSQL, with disclosed timing/denial fixtures, including delayed/out-of-order attempt rejection |
| Fulfillment condition persistence across version skew | FR-1 / IC-2 | Component integration / DEV OSAC-Core | TC-FR1-08; real DAO serialization/deserialization and PostgreSQL, documents current unrecognized-condition-type behavior |
| Fulfillment role projection and CLI visibility | FR-2 / IC-1, IC-4 | Component integration / DEV OSAC-Core | TC-FR2-01, TC-FR2-03; real API/auth/database/CLI, controlled condition outcomes |
| Fulfillment API/event redaction and reason/message sanitization | FR-2 / IC-1 | Component integration / DEV OSAC-Core | TC-FR2-04; real serialization and event path, synthetic credentials and unsafe-text fixtures |
| UI visibility and result labels | FR-2, FR-4 / IC-1, IC-5 | Unit / DEV OSAC-Core UI | TC-FR2-05, TC-FR4-01–02; Vitest/mocked transport, no live authorization claim |
| UI event-triggered reads | FR-3 / IC-3, IC-5 | Unit / DEV OSAC-Core UI | TC-FR3-01; mocked stream/read, no deployed transport claim |
| Fulfillment CLI event/read path | FR-3 / IC-3, IC-4 | Component integration / DEV OSAC-Core | TC-FR3-02; deployed API/Kafka/CLI, controlled source changes |
| Fulfillment reconnect resynchronization | FR-3 / IC-3 | Component integration / DEV OSAC-Core | TC-FR3-03; real watch/Kafka client, controlled disconnect and missed update |
| Operator-to-Fulfillment producer feedback and API/CLI journey | FR-1, FR-3 / IC-1, IC-2, IC-3, IC-4 | E2E / QE OSAC-Core | TC-FR3-04; real owning controllers, feedback/Signal, persistence and clients, controlled source job/provider outcomes, including delayed/out-of-order attempt rejection |
| UI browser event delivery and reconnect | FR-2, FR-3 / IC-1, IC-3, IC-5 | E2E / QE OSAC-Core UI | TC-FR3-05; real browser/UI/proxy/ingress/auth/API/Kafka, controlled onboarding source outcomes |

## Test Cases

### FR-1: Aggregate networking, workload storage, Secret Storage, and breakglass

#### TC-FR1-01: All four components succeed

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2 | critical | automated |

##### Preconditions

- The projector receives `Succeeded` for networking, workload storage, Secret Storage, and
  breakglass.

##### Steps

1. Calculate the onboarding projection for the Tenant.

##### Expected Results

- The overall status is `ON_BOARDED`.
- The admin component list contains exactly the four minimal requirements and
  each state is `SUCCEEDED`.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Unit — `[DEV]` OSAC-Core.
- **Suite:** Proposed `fulfillment-service/internal/controllers/tenant/onboarding_status_test.go`.
- **Command:** Proposed, from `fulfillment-service/`:
  `ginkgo run --timeout 20m --focus 'Tenant onboarding status' internal/controllers/tenant`.
- **Prerequisites:** Go test environment only.
- **Boundary:** Pure aggregation/projector logic. All four source conditions
  are fixtures; no database, Vault, Kubernetes, or provider runs for real.

#### TC-FR1-02: Failure takes precedence over progress

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2 | critical | automated |

##### Preconditions

- One component is `FAILED`; a different component is `IN_PROGRESS`.

##### Steps

1. Calculate the onboarding projection for the Tenant.

##### Expected Results

- The overall status is `FAILED`.
- The failing component remains `FAILED`; the pending component remains
  `IN_PROGRESS` in the admin breakdown.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Unit — `[DEV]` OSAC-Core.
- **Suite:** Proposed `fulfillment-service/internal/controllers/tenant/onboarding_status_test.go`.
- **Command:** Proposed, from `fulfillment-service/`:
  `ginkgo run --timeout 20m --focus 'Tenant onboarding status' internal/controllers/tenant`.
- **Prerequisites:** Go test environment only.
- **Boundary:** Pure precedence function; statuses and reasons are fixtures.

#### TC-FR1-03: Pending and unavailable inputs map separately

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2 | high | automated |

##### Preconditions

- Table entries provide either a pending component with no failures, or an
  unavailable/unknown component.

##### Steps

1. Calculate the onboarding projection for each table entry.

##### Expected Results

- Pending with no failure produces overall `IN_PROGRESS`.
- An unavailable/unknown component produces overall `FAILED`, in accordance
  with the PRD's unavailable rule.
- The admin component list identifies which component supplied the state.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Unit — `[DEV]` OSAC-Core.
- **Suite:** Proposed `fulfillment-service/internal/controllers/tenant/onboarding_status_test.go`.
- **Command:** Proposed, from `fulfillment-service/`:
  `ginkgo run --timeout 20m --focus 'Tenant onboarding status' internal/controllers/tenant`.
- **Prerequisites:** Go test environment only.
- **Boundary:** Aggregation logic uses fixture conditions. This does not prove
  a live Vault, workload-storage, or networking observation.

#### TC-FR1-04: Breakglass reports completion through the existing Vault prerequisite

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2 | critical | automated |

##### Preconditions

- Fixtures represent the existing flow with Vault integration configured:
  completed IDP identity creation and credential persistence with a saved
  Secret reference; `VAULT_READY=False` with `ProvisionFailed`;
  `VAULT_READY=True` while credential persistence is still pending; and a
  credential persistence failure after Vault setup succeeded.
- The other three components are successful in every case.

##### Steps

1. Calculate the breakglass component state for each case.
2. Calculate the overall state with the other three components successful.

##### Expected Results

- `VAULT_READY=True` produces Secret Storage `SUCCEEDED`, independently of
  whether the subsequent required credential write succeeds.
- Completed identity creation and credential persistence, with the saved
  Secret reference and successful breakglass condition, produce Breakglass
  `SUCCEEDED` and overall `ON_BOARDED`. These fixtures reflect the existing
  Vault gate; no new provisioning behavior or named key is required.
- `VAULT_READY=True` alone, without persisted credentials and their reference,
  cannot produce breakglass `SUCCEEDED` or overall `ON_BOARDED`.
- A credential persistence failure after Vault setup succeeded leaves Secret
  Storage `SUCCEEDED` but produces Breakglass `FAILED`, overall `FAILED`, and
  a sanitized reason visible to Cloud Provider Admins.
- A failed Vault provisioning outcome with `ProvisionFailed` produces Secret
  Storage `FAILED` and overall `FAILED`; Breakglass cannot be `SUCCEEDED`.
  Cloud Provider Admins receive the underlying reason. Without a confirmed new
  active attempt, future retry eligibility does not change this failed result;
  the active/waiting transitions are covered explicitly in TC-FR1-07.
- Initial pending persistence without a failed result, or a confirmed new
  active write, is `IN_PROGRESS` and cannot produce `ON_BOARDED`.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Unit — `[DEV]` OSAC-Core.
- **Suite:** Proposed `fulfillment-service/internal/controllers/tenant/onboarding_status_test.go`.
- **Command:** Proposed, from `fulfillment-service/`:
  `ginkgo run --timeout 20m --focus 'Tenant onboarding status' internal/controllers/tenant`.
- **Prerequisites:** Go test environment; fixture Secret reference and
  `VAULT_READY` condition.
- **Boundary:** Projection/mapping only, including failure reporting for the
  existing persistence flow. All Vault and Secret outcomes are fixtures; this
  case does not exercise real Vault provisioning or credential storage.

#### TC-FR1-05: Real Vault setup and required credential persistence

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2 | critical | automated |

##### Preconditions

- A deployed component-integration environment runs real Fulfillment API and
  reconciliation, PostgreSQL, Keycloak, and the supported Vault/OpenBao backend.
- Tenant-scoped denial fixtures can cause real Vault provisioning or credential
  write rejection in an isolated test namespace/deployment. Building these
  fixtures is part of the DEV work; shared production or unrelated tenant
  permissions must not be changed. No mock SecretStore is used.
- A test-owned passthrough gate can delay a selected real Vault operation
  while allowing other requests through. It controls test timing only, not a
  mocked success result. Producer start evidence must be persisted before the
  call completes for the active-attempt assertion to pass.
- A second, independent passthrough gate and a controlled interruption/takeover
  trigger (e.g., forcing a new reconcile to claim the operation) allow two
  competing attempts (A, then superseding B) to exist for the same operation
  slot, so delayed completions from A can be released after B is current.
- Networking/workload-storage evidence is controlled; their provisioning is
  outside this case. An authorized private client can inspect completion
  evidence and a provider principal can read the projected public status.

##### Steps

1. Create a Tenant through the deployed API and let real reconciliation create
   the IDP/breakglass identity, provision its Vault namespace, and store the
   required credential Secret.
2. Read the Tenant through the private and public APIs. Fetch the referenced
   Secret through the existing authorized Secrets API for a test assertion;
   do not add a new onboarding read-back probe or log credential values.
3. Repeat with an isolated fixture that makes Vault provisioning fail after
   the IDP identity has been created.
4. Repeat with provisioning successful but a tenant-scoped Vault fixture that
   rejects the required credential write. Read the failed result again during
   reconciliation/backoff without a new attempt and confirm it remains Failed.
5. Let normal reconciliation start a fresh credential write. A request-specific
   passthrough gate holds the real Vault request until the test releases it.
   Read the public Tenant while that operation is active, then release the
   gate and check the resulting failure or success.
6. Start attempt A for a credential write and confirm its attempt ID and
   active evidence are persisted before A's call completes. Through the
   controlled interruption/takeover trigger, make attempt B current for the
   same operation and confirm B's active evidence is persisted. Release A's
   held response as success, then repeat as failure, then repeat as a
   progress/active signal; after each, confirm B's evidence is unchanged.
   Complete B, then replay A's response again and confirm no change. Finally,
   force B's registration to race with A's identity check immediately before
   A's save and confirm the version-preconditioned write conflicts and is
   rejected on re-check rather than retried with a refreshed version.

##### Expected Results

- The successful case records `VAULT_READY=True`, a nonempty breakglass user
  ID, completed breakglass evidence, and a saved Secret reference. The public
  provider view shows Secret Storage and Breakglass `SUCCEEDED`.
- The existing Secrets API retrieves the credentials through the real backend;
  values are compared in memory only. PostgreSQL stores Secret metadata and
  the Tenant reference rather than the Secret payload.
- A failed Vault setup leaves Secret Storage failed, retains the already
  created IDP identity, and cannot produce a successful Breakglass component
  or overall `ON_BOARDED`.
- A rejected credential write after setup leaves Secret Storage successful,
  records a sanitized Breakglass failure reason, and cannot produce overall
  `ON_BOARDED`.
- A saved failure remains `FAILED` while another attempt is only possible,
  queued, or delayed. Beginning the actual next write publishes `IN_PROGRESS`
  before the held operation returns; saving start evidence only together with
  the final result does not satisfy this assertion. The result then becomes
  `FAILED` or `SUCCEEDED`, and the aggregate follows the existing precedence.
- Once attempt B is current, none of attempt A's delayed success, failure, or
  progress responses change B's persisted evidence, reason, timestamps, or
  Secret reference; a duplicate terminal result for an already-completed
  attempt is a no-op. A write whose attempt identity loses the version-
  preconditioned race is rejected and re-checked against the now-current
  attempt, never retried by simply refreshing the object version and
  reapplying the stale result.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Component integration — `[DEV]` OSAC-Core.
- **Suite:** Proposed extensions to existing
  `fulfillment-service/it/it_tenant_lifecycle_test.go` and
  `fulfillment-service/it/it_public_secrets_test.go`. Existing tests inspect
  persisted breakglass references and retrieve Secret data; they do not yet
  verify the proposed onboarding projection or these new denial fixtures.
- **Command:** From repository root:
  `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`.
- **Prerequisites:** Compatible disposable Kind profile, the real services
  above, test identities, tenant-isolated Vault denial fixtures, a
  request-specific passthrough timing gate, and a controlled
  interruption/takeover trigger able to make a second attempt current, all
  supplied by the DEV work.
- **Boundary:** Tenant API -> reconciliation -> Keycloak/Vault -> Secrets API
  and PostgreSQL are real. The Vault timing gate, the interruption/takeover
  trigger, and network/workload-storage readiness are controlled fixtures; no
  network or storage-provider provisioning is claimed.

#### TC-FR1-06: On-Boarded status can regress and recover

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2 | high | automated |

##### Preconditions

- Source-condition fixtures initially report all four requirements successful.
- Cases represent reported failure, pending, and recovery outcomes; they do
  not simulate continuous monitoring or change a latched source producer.

##### Steps

1. Read/project the Tenant and confirm overall `ON_BOARDED`.
2. Change one reported component condition to a failed outcome and project
   again for Cloud Provider Admin, Tenant Admin, and Tenant User.
3. In a separate case, change one component to pending with no failures.
4. Restore all four components to success and project again.

##### Expected Results

- Failed/unavailable evidence changes the admin aggregate to `FAILED` and
  tenant-role aggregate to `NOT_ONBOARDED`; the affected component is identified
  only in the permitted admin detail.
- Pending evidence without a failure changes the admin aggregate to
  `IN_PROGRESS` and tenant-role aggregate to `NOT_ONBOARDED`.
- Restored all-success evidence returns every role to `ON_BOARDED` with its
  permitted detail. The aggregate does not retain its earlier successful value.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Unit — `[DEV]` OSAC-Core.
- **Suite:** Proposed shared projector tests in
  `fulfillment-service/internal/controllers/tenant/onboarding_status_test.go`.
- **Command:** From `fulfillment-service/`:
  `ginkgo run --timeout 20m --focus 'Tenant onboarding status' internal/controllers/tenant`.
- **Prerequisites:** Go test environment and role/condition fixtures.
- **Boundary:** Pure projection/role mapping with synthetic source transitions.
  No real Vault, hub, provider, event stream, or browser is exercised; the
  connected-view behavior is planned separately in TC-FR3-01.

#### TC-FR1-07: Failed attempts remain visible until another attempt actually starts

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2 | critical | automated |

##### Preconditions

- Parameterized normalization/projector fixtures cover all four requirements.
- Each fixture identifies the current operation/job, its last result, and
  confirmed activity. Other requirements are successful unless specified.
- No failure is inferred solely from an enum name; a queued rerun without a
  failed result is distinguished from backoff following a failed attempt.

##### Steps

1. Project initial pending work with no failure, then a confirmed active
   attempt with no result yet.
2. Record its failure. Re-read while future retries are allowed, queued, or
   delayed and while a poll only rechecks the same failed job.
3. Record the actual start of a new attempt for that operation, followed by
   another failure and then a further active attempt that succeeds.
4. Exercise an unrelated failed required child while another child is active.
5. Present a stale/interrupted running marker without confirmed current work;
   also present an older result after a newer attempt/result is authoritative.

##### Expected Results

- Initial pending and confirmed active attempts produce `IN_PROGRESS` when
  no other required failure exists.
- A completed failed result produces `FAILED` and stays failed throughout
  backoff/eligibility/polling, regardless of how long future retries remain
  allowed. No common retry cap or timeout is added by the display function.
- Only confirmed start of a newer attempt returns that operation to
  `IN_PROGRESS`. Its failure returns `FAILED`; its successful completion plus
  all other successes produces `ON_BOARDED`.
- An unrelated child's current failure still wins over another child's
  activity. Initial queued work without a failed result is not labeled Failed
  merely because a source enum calls it Retrying.
- Stale/unconfirmed activity cannot hold `IN_PROGRESS`; unavailable or
  interrupted evidence follows failure rules. An older result cannot replace
  the authoritative current attempt/outcome.
- Tenant Admin/User receive only `NOT_ONBOARDED` until all requirements
  succeed. Admin detail and failure reasons follow their existing role scope.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Unit — `[DEV]` OSAC-Core, with owning controller reporting
  changes in the affected Fulfillment/operator work.
- **Suite:** Proposed shared normalization/projector cases in
  `fulfillment-service/internal/controllers/tenant/onboarding_status_test.go`.
- **Command:** From `fulfillment-service/`:
  `ginkgo run --timeout 20m --focus 'Tenant onboarding status' internal/controllers/tenant`.
- **Prerequisites:** Go test environment; condition, job/operation, and role
  fixtures.
- **Boundary:** Pure normalization/projection with synthetic evidence. It does
  not prove that real producers publish activity, persist before I/O, handle
  controller interruption, or deliver browser events. TC-FR1-05 and the stated
  producer/feedback integration gap cover those required boundaries.

#### TC-FR1-08: An unrecognized private condition type is not silently corrupted across a mixed-version read/write

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- A real Fulfillment instance with PostgreSQL, using the actual DAO
  serialization/deserialization path (`internal/database/dao`,
  `internal/json/json_encoder.go`), not a mock store.
- A Tenant record persisted with a condition whose `type` is a name the
  running binary's proto registry does not recognize (simulating an old
  replica reading data written by a newer one), alongside at least one other,
  recognized condition on the same Tenant.
- A separate Tenant fixture already has `spec.break_glass_credentials_secret`
  set (simulating a tenant that completed Breakglass persistence before this
  condition type existed, or during a rollback) and has no
  `BREAK_GLASS_CREDENTIALS_READY` condition at all.

##### Steps

1. Persist the Tenant record containing the unrecognized condition type name
   directly at the storage boundary (not through a code path that already
   knows the new enum value).
2. Read the Tenant through the real private Get path and inspect the decoded
   condition list.
3. Through the real update path, save an unrelated field on the same Tenant
   (a change that does not touch the unrecognized condition).
4. Re-read the Tenant and inspect the condition list again.
5. Reconcile the separate Tenant fixture that already has the Secret
   reference but no Breakglass condition, through the real reconcile path,
   and read its resulting condition and public onboarding projection.

##### Expected Results

- After step 2, the decoded condition for the unrecognized type is present in
  the list, but its `type` cannot be relied on to equal the original intended
  value — document and assert whatever the current decode path actually
  produces (`UNSPECIFIED` with `DiscardUnknown: true` is the known current
  behavior); this is evidence of present behavior, not an endorsement of it.
- The other, recognized condition is unaffected and still reads correctly.
- After step 3's save, assert whether the unrecognized condition's original
  type identity is preserved or lost in the re-read. If the implementation
  does not yet include a persistence-compatibility fix, this case is expected
  to fail, documenting the gap explicitly rather than passing on an
  unverified assumption; once the fix lands, this case must pass before the
  new condition type is enabled for a rolling upgrade.
- After step 5, the fixture tenant's Breakglass condition reaches the correct
  ready value and the public projection reflects it, even though its
  credential persistence path finds the Secret reference already saved and
  would otherwise skip the work that sets the condition. If the
  implementation does not yet reassert or otherwise establish the condition
  for already-completed tenants, this assertion is expected to fail,
  documenting the gap rather than assuming it is covered.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below. This
  case also validates whatever persistence-compatibility fix DEV work
  produces for the gap described in §Upgrade / Downgrade Strategy; it is not
  itself proof that such a fix exists today.
- **Tier / owner:** Component integration — `[DEV]` OSAC-Core.
- **Suite:** Proposed `fulfillment-service/it/it_tenant_condition_skew_test.go`.
- **Command:** Proposed, from repository root:
  `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`.
- **Prerequisites:** Deployed Fulfillment and PostgreSQL; a way to insert a
  raw condition value at the storage boundary that the running binary's proto
  registry does not recognize; a Tenant fixture with
  `break_glass_credentials_secret` already set and no Breakglass condition.
- **Boundary:** Exercises the real JSON encode/decode, DAO read/update, and
  reconcile paths against a real database. It does not run two different
  Fulfillment binary versions side by side; it validates the serialization
  mechanism that determines cross-version behavior, which is
  version-independent, and the reconcile idempotency path that determines
  whether an already-completed tenant's condition gets established. It does
  not cover the operator CRD's separate string-based condition
  representation.

### FR-2: Apply the same role visibility in API, CLI, and UI

#### TC-FR2-01: Tenant roles receive only the binary indicator

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-4 | critical | automated |

##### Preconditions

- Authenticated Tenant Admin and Tenant User identities can read their own
  Tenant. Test data includes pending, failed, and fully successful onboarding.

##### Steps

1. Read the Tenant through public `Tenants.Get` and `Tenants.List` as each role.
2. Run `osac get tenants -o json` as each role.

##### Expected Results

- Pending and failed tenants show `NOT_ONBOARDED`; an all-success Tenant shows
  `ON_BOARDED`.
- `components`, `reason`, and `message` are absent from both API and CLI output.
- A caller cannot read another tenant's onboarding status.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Component integration — `[DEV]` OSAC-Core.
- **Suite:** Proposed `fulfillment-service/it/it_tenant_onboarding_status_test.go`.
- **Command:** Proposed, from repository root:
  `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`.
- **Prerequisites:** Compatible deployed Kind profile, Fulfillment, PostgreSQL,
  Keycloak, and test identities for Tenant Admin and Tenant User.
- **Boundary:** Public Fulfillment APIs, auth, database, and CLI are real;
  onboarding component statuses are fixture-controlled. No network or storage
  provider workflow is asserted.

#### TC-FR2-03: Cloud Provider Admin receives full failure reasons

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-4 | high | automated |

##### Preconditions

- A failed component has a machine reason and a sanitized human-readable
  failure message.
- Source data also includes broader compute-readiness and monitoring evidence
  that is outside the four minimal onboarding requirements.

##### Steps

1. Read the Tenant through API and CLI as a Cloud Provider Admin.

##### Expected Results

- The onboarding projection includes exactly the four minimal component
  states; broader compute-readiness and monitoring evidence is excluded.
- The failed component includes its reason and full approved failure message.
- No user-triggered retry field or command is present.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Component integration — `[DEV]` OSAC-Core.
- **Suite:** Proposed `fulfillment-service/it/it_tenant_onboarding_status_test.go`.
- **Command:** Proposed, from repository root:
  `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`.
- **Prerequisites:** Compatible deployed Kind profile, Fulfillment,
  PostgreSQL, Keycloak, Kafka, and a Cloud Provider Admin test identity.
- **Boundary:** Public/private Tenants APIs, authorization, PostgreSQL, and CLI
  are real; component failure input is fixture-controlled. The test asserts
  returned status content, not a real provider failure.

#### TC-FR2-04: Status projection excludes credentials, private conditions, and raw provider text

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Private Tenant status contains breakglass credentials, internal IDP fields,
  raw conditions, and a failure message.
- A fixture private condition's stored `reason`/`message`, as an existing
  writer could produce it today, contains a synthetic Vault request URL, a
  synthetic backend response body, a synthetic token/password-shaped string,
  and an unrecognized reason code — none of these are approved output text.

##### Steps

1. Read the Tenant through public Get/List and public `Events.Watch`.
2. Inspect the serialized Tenant and event payload for sensitive/private data.
3. Read the same Tenant as `cloud-provider-admin`, who is entitled to
   component states and failure reasons.

##### Expected Results

- The public status contains only the role-approved onboarding projection.
- `break_glass_credentials`, Secret contents, IDP internals, and raw conditions
  are absent.
- The public Tenant event contains no component details or failure messages;
  `Events.Watch` acts only as an invalidation signal, followed by a role-scoped
  Get.
- The Cloud Provider Admin response contains only the approved reason/message
  pair for the matching component/outcome, or the approved generic pair if the
  reason is unrecognized. The fixture's raw Vault URL, backend response body,
  token/password-shaped string, and unrecognized reason code are absent, even
  though they exist in the underlying stored private condition.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Component integration — `[DEV]` OSAC-Core.
- **Suite:** Proposed tenant projection cases in
  `fulfillment-service/it/it_tenant_onboarding_status_test.go`; extend
  `fulfillment-service/internal/servers/event_publisher_test.go` for event
  redaction if the public event payload is changed.
- **Command:** Proposed, from repository root:
  `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`.
- **Prerequisites:** Deployed Fulfillment, PostgreSQL, Kafka, and a seeded
  private Tenant with test-only credentials.
- **Boundary:** API/event serialization, role filtering, and the admin-visible
  reason/message mapping are real; the credentials and the unsafe fixture
  condition text are synthetic test data. No external Vault token is used.

#### TC-FR2-05: UI renders the role-specific status scope

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- UI fixtures provide each role's projected Tenant response for an all-success
  and a failed Tenant.

##### Steps

1. Render the tenant admin/provider list and the tenant workspace for each role.
2. Inspect visible status labels, component details, and failure actions.

##### Expected Results

- Provider Admin sees the component breakdown and failure reason.
- Tenant Admin/User see only `Not On-Boarded` or `On-Boarded`.
- No view includes a retry control.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Unit — `[DEV]` OSAC-Core (UI).
- **Suite:** Existing `osac-ui/libs/ui-components/src/components/Tenant/TenantListPage.test.tsx` plus proposed `TenantOnboardingStatus.test.tsx`.
- **Command:** `pnpm test` from `osac-ui/`.
- **Prerequisites:** Node/pnpm dependencies installed.
- **Boundary:** Vitest and mocked Connect responses; this verifies rendering
  and not live authorization or streaming.

### FR-3: Update status automatically without manual refresh

#### TC-FR3-01: UI refetches after a Tenant event

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3, IC-5 | high | automated |

##### Preconditions

- The UI is displaying a Tenant and has an active `Events.Watch` subscription.
- The Connect test transport can emit a Tenant `OBJECT_UPDATED` event.
- Parameterized cases provide Tenant Admin/User and Cloud Provider Admin
  response fixtures. Tenant roles initially receive
  `NOT_ONBOARDED`; admin fixtures initially show `IN_PROGRESS`.

##### Steps

1. Emit a matching Tenant event and return an updated role-scoped Get response
   with overall `ON_BOARDED` for the all-components-success case.
2. In a separate admin case, emit an event when storage changes to `SUCCEEDED`
   while another component remains pending and overall stays `IN_PROGRESS`.
3. In a provider-admin failure case, emit an event and return a failed
   component with its approved failure reason.
4. In a regression case, start from `ON_BOARDED`, emit a reported component
   failure event, and return `FAILED` for admins or `NOT_ONBOARDED` for tenant
   roles. Restore all conditions and emit a recovery event.
5. Emit a retry-scheduled notification with the component still failed, then
   an actual-attempt-start notification with it in progress, followed by the
   attempt result. Each Get response carries only the caller's permitted data.

##### Expected Results

- The UI starts a role-scoped Tenant read as soon as each matching event
  arrives; it does not wait for a polling interval or manual refresh.
- Tenant Admin/User views change from `Not On-Boarded` to `On-Boarded` after
  the all-components-success response, with no component details exposed.
- The Cloud Provider Admin view updates the storage component from
  `In Progress` to `Succeeded` even though overall remains `In Progress`.
- Cloud Provider Admin sees the returned failure reason for a failed
  component; other roles receive only their permitted status detail.
- After an already onboarded Tenant's condition changes to failed, the view
  automatically returns to `Failed` for admins or `Not On-Boarded` for tenant
  roles; the recovery event restores `On-Boarded` without a manual refresh.
- A retry-scheduled event retains Failed in admin views; only an actual-start
  event returns the component to In Progress. Failure/success result events
  update it again. Tenant roles retain the binary indicator throughout.
- No polling interval is required for these connected-session cases.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Unit — `[DEV]` OSAC-Core (UI).
- **Suite:** Proposed `osac-ui/libs/ui-components/src/components/Tenant/TenantOnboardingStatus.test.tsx`.
- **Command:** `pnpm test` from `osac-ui/`.
- **Prerequisites:** Vitest, Testing Library, and mocked Connect event/Get
  transport.
- **Boundary:** The event stream and API are doubles; this does not prove the
  Go proxy or Kafka delivery boundary.

#### TC-FR3-02: CLI watch re-reads the updated Tenant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3, IC-4 | high | automated |

##### Preconditions

- A CLI principal can read a Tenant and start `Events.Watch`.
- The Tenant update changes the onboarding projection.

##### Steps

1. Run `osac get tenants --watch` for the target Tenant.
2. Change a component condition through the deployed Tenant status path.

##### Expected Results

- The CLI receives the update event, re-reads the Tenant, and prints the new
  role-scoped status as soon as the event arrives, without waiting for a
  polling interval or requiring the user to rerun `osac get`.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Component integration — `[DEV]` OSAC-Core.
- **Suite:** Proposed `fulfillment-service/it/it_tenant_onboarding_status_test.go`.
- **Command:** Proposed, from repository root:
  `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`.
- **Prerequisites:** Compatible Kind profile with Fulfillment, PostgreSQL,
  Keycloak, Kafka, test CLI credentials, and an operator Tenant CR.
- **Boundary:** Deployed API, database, event publisher, Kafka watch, and CLI
  are real; condition change is fixture-controlled. No external network or
  storage provider workflow is run.

#### TC-FR3-03: Reconnect refreshes current status after missed events

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | medium | automated |

##### Preconditions

- A client has an active Tenant status view and a controllable event stream.
- A Tenant update occurs while the client is disconnected.

##### Steps

1. Disconnect the event stream.
2. Change the Tenant's component status.
3. Reconnect the stream and run the designed resynchronization path.

##### Expected Results

- The client issues a fresh Tenant Get and displays the current status even
  though the event produced while disconnected was not delivered.
- The current Tenant value, not an event payload, determines the displayed
  state.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Component integration — `[DEV]` OSAC-Core.
- **Suite:** Proposed event/status cases in
  `fulfillment-service/it/it_tenant_onboarding_status_test.go`.
- **Command:** Proposed, from repository root:
  `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`.
- **Prerequisites:** Deployed Fulfillment, PostgreSQL, Kafka, and a reconnectable
  Events.Watch test client.
- **Boundary:** Real Events.Watch server and Kafka; the test controls stream
  disconnect and Tenant update. It does not measure a numeric latency SLA.

#### TC-FR3-04: Deployed status change reaches API and CLI clients

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2, IC-3, IC-4 | critical | automated |

##### Preconditions

- A source-pinned OSAC test environment has Fulfillment, the Operator,
  PostgreSQL, Keycloak, Kafka, and Vault/OpenBao available.
- Test identities exist for tenant and provider roles. Component condition
  changes are controlled by test fixtures. Real Vault setup and required
  credential persistence are covered separately by TC-FR1-05; encryption-key
  provisioning is outside the revised scope.

##### Steps

1. Create a test Tenant and wait for its initial Tenant record.
2. For Networking and Workload Storage, drive test-controlled source
   job/operation outcomes through active, failed, waiting/backoff, a confirmed
   new attempt, and success. Let the real owning controller and feedback path
   persist Tenant evidence; do not patch the final Tenant readiness conditions
   or call Signal directly as a substitute for the producer/watch boundary.
3. Interrupt an active operation and supply its real source cancellation or
   terminal outcome. Verify that stale activity does not remain In Progress.
4. For one of Networking or Workload Storage, let a job fail, then start a
   second job (a new, distinct `JobID`/attempt) for the same operation. After
   the second job is confirmed active, deliver the first (old) job's terminal
   outcome to the source status out of order, through its real source
   update/watch path, not by patching Tenant evidence directly.
5. Observe the update through `Events.Watch`, public Tenant Get, and
   `osac get tenants --watch` without issuing a manual refresh.

##### Expected Results

- The event stream delivers a Tenant update while connected.
- Real producer/feedback evidence reaches the Tenant API/database. Active
  work is IN_PROGRESS; completed failure remains FAILED during waiting and
  changes back only when a new attempt starts. A cancelled/interrupted attempt
  with no current work cannot retain an active marker. Another required
  child's failure still wins.
- Subsequent role-scoped Get and CLI output show the component and aggregate
  status; tenant roles receive only the binary indicator.
- The old job's delayed terminal outcome does not change the status set by
  the second job's attempt — the real controller/feedback path rejects it by
  job/attempt identity rather than applying whichever outcome arrives last.
- The test uses a bounded `Eventually` timeout as a harness hang limit; it
  does not define a product latency SLA.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** E2E — `[QE]` OSAC-Core; QE issue owner and follow-up Task are not
  assigned yet.
- **Suite:** Proposed `tests/e2e/regression/test_tenant_onboarding_status.py`.
- **Command:** Proposed, from repository root:
  `uv run pytest -n 0 tests/e2e/regression/test_tenant_onboarding_status.py`.
- **Prerequisites:** Source-pinned deployed test environment, Keycloak test
  identities, PostgreSQL, Kafka, Vault/OpenBao, and hub access to change Tenant
  condition evidence.
- **Boundary:** Fulfillment API/database, Keycloak, event publisher/Kafka,
  Operator feedback, and CLI are real. Network/workload-storage/Secret Storage source outcomes are
  controlled at the source job/result boundary; the real owning controller,
  Tenant persistence, watch/Signal feedback, and event delivery must run. AAP
  job outcomes and external network/storage-provider execution are simulated,
  including the out-of-order delivery of an old job's terminal outcome after a
  newer job is current; no provider provisioning is claimed. Real Vault
  setup/persistence is planned in TC-FR1-05. Extend the proposed suite to
  provide this source-outcome harness; existing condition-only fixtures are
  insufficient.

#### TC-FR3-05: Browser refresh and missed-event recovery through deployed UI

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-3, IC-5 | critical | automated |

##### Preconditions

- A deployed UI uses the actual proxy/ingress, Fulfillment API and controllers,
  PostgreSQL, Keycloak sessions, and Kafka Events.Watch service.
- Separate browser sessions authenticate as `cloud-provider-admin`,
  `tenant-admin`, and `tenant-user` for one disposable test Tenant.
- The proposed test config disables fallback polling and browser focus-refetch
  for the onboarding queries; other feature queries are unchanged. Test-owned
  condition evidence may be changed through the deployed backend fixture.

##### Steps

1. Open the provider Tenant view and tenant workspace in their separate
   sessions. Confirm the Events.Watch request is open before changing data.
2. Make one requirement succeed while another is still pending. Observe a
   delivered Tenant event and the fresh Tenant read in the provider session.
3. Make all four requirements succeed. Observe the resulting read and labels
   in each session without clicking, navigating, focusing, or refreshing.
4. Disconnect the browser network. Change a component to failed while the
   browser is offline, then restore the connection. Observe reconnection and
   the recovery Tenant read despite the missed event.
5. Restore the failed component and verify recovery. Inspect serialized reads
   for each role and check that no status view offers Retry.

##### Expected Results

- For connected changes, a Tenant read starts after each matching event and
  before any fallback polling or focus trigger. The provider component updates
  even when the aggregate remains IN_PROGRESS.
- With all four successful, each session shows On-Boarded. After the missed
  failure, reconnection triggers a fresh read; the provider sees Failed and
  its sanitized reason, while tenant sessions show only Not On-Boarded.
- Tenant reads and pages expose no components, progress, or failure reason.
  Recovery restores On-Boarded. No user-triggered Retry control is present.
- Playwright trace/network evidence records event receipt, Tenant reads,
  disconnect/reconnect, and rendered outcomes. A proposed 60-second assertion
  timeout per transition is a test hang bound, not a product latency SLA;
  fallback polling must not satisfy an event-path assertion.

##### Coverage Evidence

- **Execution status:** Planned, not run; new harness/config still required.
- **Tier / owner:** E2E — `[QE]` OSAC-Core/UI work; no individual or Task is
  assigned yet. This is an explicit implementation dependency.
- **Suite:** Proposed persisted
  `osac-ui/apps/e2e-tests/src/tenant-onboarding.spec.ts` and
  `osac-ui/apps/e2e-tests/playwright.onboarding.config.ts`. Existing
  `src/vmaas/create.tenant.spec.ts` and the shared `openAndLogin` and Tenant
  page helpers provide login/navigation patterns. Do not place the regression
  in the throwaway `apps/playwright/specs` harness.
- **Command:** Proposed, from `osac-ui/`:
  `pnpm --filter @osac/e2e-tests exec playwright test --config playwright.onboarding.config.ts src/tenant-onboarding.spec.ts`.
- **Prerequisites:** Installed pnpm/Playwright/browser dependencies, deployed
  UI URL, test role sessions, disposable tenant, backend condition fixture,
  and control over browser connectivity and query polling. The proposed config
  and role fixtures do not exist yet; no owner/ticket has been assigned.
- **Boundary:** Real browser, production UI subscription/reconnect code,
  proxy/ingress, sessions, Fulfillment, database, and event service/Kafka.
  Onboarding source outcomes are fixture-controlled; external network/storage
  providers and Vault provisioning are omitted from this UI-delivery case.
  No mocked Connect transport or fake Fulfillment server satisfies this case.

### FR-4: Show simple progress and the attempt result; do not offer retry

#### TC-FR4-01: Component progress has no detailed subprogress

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-5 | medium | automated |

##### Preconditions

- A component response transitions from `IN_PROGRESS` to `SUCCEEDED`.

##### Steps

1. Render the admin status view with the component in progress.
2. Return a successful component state and re-render.

##### Expected Results

- While progressing, the component shows only `In Progress`; no step-level
  progress is visible.
- On completion, the component shows `Succeeded` and the overall state becomes
  `On-Boarded` when the other three components have also succeeded.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Unit — `[DEV]` OSAC-Core (UI).
- **Suite:** Proposed `osac-ui/libs/ui-components/src/components/Tenant/TenantOnboardingStatus.test.tsx`.
- **Command:** `pnpm test` from `osac-ui/`.
- **Prerequisites:** Vitest fixtures for component states.
- **Boundary:** UI mapping only; server state transitions are covered by FR-1
  and FR-3 cases.

#### TC-FR4-02: Failure reason is scoped to Cloud Provider Admin; no retry control

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-5 | high | automated |

##### Preconditions

- A component is failed with a reason and human-readable message.

##### Steps

1. Render the status view for Cloud Provider Admin, Tenant Admin, and
   Tenant User.
2. Inspect the status detail and available controls for each role.

##### Expected Results

- Cloud Provider Admin sees the full failure reason.
- Tenant Admin/User see only `Not On-Boarded`.
- No view includes a retry control.

##### Coverage Evidence

- **Execution status:** Planned, not run. Implementing Tasks are not yet
  decomposed or assigned; no follow-up ticket exists unless noted below.

- **Tier / owner:** Unit — `[DEV]` OSAC-Core (UI); server projection is also
  covered by TC-FR2-01, TC-FR2-03, and TC-FR2-04.
- **Suite:** Proposed `osac-ui/libs/ui-components/src/components/Tenant/TenantOnboardingStatus.test.tsx`.
- **Command:** `pnpm test` from `osac-ui/`.
- **Prerequisites:** Role-specific status fixtures.
- **Boundary:** UI component and mock responses; role authorization itself is
  exercised by the Fulfillment component-integration cases.

## Gaps

### Requirement Coverage Gaps

- **FR-1 attempt activity reporting:** TC-FR1-07 covers synthetic mapping,
  TC-FR1-05 plans real Vault/Breakglass start/result persistence and the
  per-attempt identity guard against delayed/out-of-order completions
  (including a version-preconditioned write race), and TC-FR3-04 now
  explicitly plans the real controller/feedback path for network and
  workload-storage source jobs, including interrupted attempts and an old
  job's delayed outcome arriving after a newer job is current. These tests
  and source-outcome fixtures are not implemented or run. No follow-up Task
  is assigned yet; do not treat condition-only fixtures as producer proof. The
  attempt-identity field(s) themselves (Vault/Breakglass opaque attempt ID;
  Storage's `patchTenantStorageStatus` identity check) are also unimplemented
  and are DEV work, not already-covered behavior.

- **FR-1 Secret Storage integration:** TC-FR1-05 specifies the required real
  Vault/Keycloak/Secrets/database boundary and DEV ownership. Its tenant-isolated
  denial fixtures and projection assertions still need implementation and
  execution; no result is claimed from unit doubles. The obsolete named-key
  contract gap is removed by the explicit scope change.

- **FR-1 condition persistence across version skew:** TC-FR1-08 documents that
  the current JSON encode/decode path does not safely preserve an unrecognized
  private condition type through a mixed-version read followed by an
  unrelated write — adding the new `BREAK_GLASS_CREDENTIALS_READY` enum value
  is not sufficient by itself. A persistence-compatibility fix (or an
  explicitly accepted, bounded display regression) is required DEV work
  before the new condition type can be safely enabled for a rolling upgrade;
  TC-FR1-08 is expected to fail until that fix lands. No follow-up Task is
  assigned yet.

- **FR-2 admin-visible message sanitization:** TC-FR2-04 now requires that the
  public projector substitute an approved reason/message pair even when the
  underlying stored condition contains unsafe text (a real risk today in
  `ensureVaultNamespace` and `projectStorageOnboardingCondition`). The
  reason-to-message mapping and the projector enforcement described in
  §Security Considerations are not yet implemented; no follow-up Task is
  assigned yet.

### Interface Change Coverage Gaps

- **IC-3/IC-5 live browser stream:** TC-FR3-05 defines the proposed deployed
  browser boundary, persisted spec/config, command, role sessions, and missed
  event assertions. Its harness and execution remain outstanding with no
  assigned individual or follow-up Task. Historical local browser/proxy probes
  used a fake backend and proof client; they are feasibility evidence only,
  not production UI/ingress/Kafka/session coverage.
- The proposed QE status E2E has no assigned owner or follow-up Task. The
  component-integration tests do not count as coverage of the deployed
  cross-component user journey until the QE case is implemented and run.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 19 |
| Critical | 10 |
| High | 7 |
| Medium | 2 |
| Low | 0 |
| Automated | 19 |
| Manual | 0 |
| Requirements with test cases | 4 / 4 |
| Interface changes with test cases | 5 / 5 |
