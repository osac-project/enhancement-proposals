# Test Plan — OSAC-63

## Source of truth and scope

This plan is aligned to the current design in
[`design.md`](design.md). If that design changes, update this plan in the
same phase. The plan covers only the first-milestone audit capability described
there: capture selected Fulfillment API calls, publish audit records
asynchronously, persist them through the Kafka consumer, and expose the scoped
`AuditRecords.List` API.

Out of scope for this plan are Keycloak events, resource-lifecycle completion
events, UI/CLI browsing, external SIEM export, cryptographic integrity checks,
and disable/re-enable or backfill behavior. A successful API call records the
API result; it does not prove that asynchronous provisioning later succeeded.

All cases below are planned, not executed. A proposed test location is not
execution evidence. The design leaves the RPC allowlist, target mappings,
time-range validation, and implementation-specific retry/queue settings open;
cases that depend on those choices are not execution-ready until the owner
resolves them.

## Traceability

The design assigns local requirement labels because the PRD has no formal FR or
NFR IDs.

| Design requirement | Planned cases |
|---|---|
| FR-1 — Capture selected Fulfillment API calls, including authentication failures and authorization denials | TC-CAP-01, TC-CAP-02, TC-CAP-03 |
| FR-2 — Attribute calls to the authenticated user | TC-CAP-02 |
| FR-3 — Record request and final response outcomes with a shared request ID | TC-CAP-03, TC-CONTRACT-01 |
| FR-4 — Provide filtered, paginated gRPC and HTTP+JSON queries | TC-API-01, TC-CONTRACT-01 |
| FR-5 — Enforce Tenant Admin and Cloud Provider Admin query scopes | TC-AUTH-01 |
| FR-6 — Record access to audit data | TC-AUDIT-01 |
| FR-7 — Exclude credential values while recording credential access | TC-SEC-01 |
| NFR-1 — Expose no API for updating or deleting audit records | TC-APPEND-01, TC-CONTRACT-01 |
| NFR-2 — Keep audit delivery failures from changing API results | TC-PUB-01, TC-PUB-02, TC-CONS-01 |
| NFR-3 — Keep audit data within the deployment jurisdiction | TC-DEPLOY-01 |
| NFR-4 — Retain audit rows indefinitely in this milestone | TC-RET-01 |

| Interface change | Planned cases |
|---|---|
| IC-1 — Public audit query API | TC-API-01, TC-AUTH-01, TC-AUDIT-01, TC-CONTRACT-01 |
| IC-2 — Shared audit record and Kafka contract | TC-CAP-02, TC-CAP-03, TC-CONTRACT-01, TC-CONS-01, TC-SEC-01 |
| IC-3 — Fulfillment API request/response capture | TC-CAP-01, TC-CAP-02, TC-CAP-03, TC-PUB-01, TC-PUB-02, TC-OBS-01 |
| IC-4 — Kafka consumer, append-only table, and scoped query | TC-CONS-01, TC-API-01, TC-AUTH-01, TC-APPEND-01, TC-RET-01 |
| IC-5 — Tenant topics, access controls, and deployment wiring | TC-KAFKA-01, TC-PUB-02, TC-APPEND-01, TC-DEPLOY-01 |

## Test cases

### TC-CAP-01: RPC selection, exclusions, and transport behavior

- **Requirements / interfaces:** FR-1; IC-3.
- **Owner / tier:** Fulfillment DEV; Unit.
- **Priority:** high.
- **Automation:** automated.

**Preconditions:** A test server can invoke the real audit interceptor chain and
control authentication, authorization, validation, handler completion, and
recovered panics. The method classification fixture identifies mapped
POST/PUT/PATCH/DELETE methods, an unmapped business RPC, a sensitive GET on the
allowlist, and an ordinary GET.

**Steps:**

1. Call each selected method through native gRPC, including the unmapped
   business RPC and sensitive GET.
2. Call a mapped method through HTTP+JSON, which routes through the gRPC server.
3. Call an ordinary GET successfully, then with authentication failure, then
   with an authenticated caller denied authorization.
4. Exercise validation failure, a recovered panic, health/reflection/transport
   probes, and a failure that occurs before a request reaches the gRPC server.

**Expected results:**

- Mapped mutations and unmapped business RPCs are selected. Sensitive GET
  selection follows the reviewed allowlist. Other GET calls are selected only
  for authentication failure or authorization denial.
- HTTP+JSON creates no duplicate pair. A successful ordinary GET creates no
  audit publication.
- Selected calls produce request/response capture attempts for their final
  gRPC result, including authentication and authorization failures.
- Excluded probes and pre-gRPC failures produce no audit publication.
- The exact production method registry and sensitive-read allowlist are
  reviewed implementation inputs; fixtures must not be treated as a finalized
  registry.

### TC-CAP-02: Authenticated attribution, tenant routing, and field minimization

- **Requirements / interfaces:** FR-1, FR-2, FR-7; IC-2, IC-3.
- **Owner / tier:** Fulfillment DEV; Unit.
- **Priority:** high.
- **Automation:** automated.

**Preconditions:** The test can provide authenticated identities, verified
target-tenant context, unverified request tenant values, and a recording
publisher. A test-only credential sentinel is available.

**Steps:**

1. Make an authenticated call where the caller differs from the object creator.
2. Make calls where the authenticated actor has a verified tenant, has no
   verified tenant, or authentication fails. Include a target in a different
   tenant and an untrusted request tenant value.
3. Make an authentication-failed call and an authorization-denied call.
4. Exercise a supported credential-access method once its action/target mapping
   is reviewed; inspect every emitted record.

**Expected results:**

- `actor` is set only from the authenticated identity. An unauthenticated call
  has no actor; an authorization denial retains the authenticated actor.
- `metadata.tenant` is the verified tenant of the authenticated actor, not the
  target object's tenant. If that tenant is unknown or authentication fails,
  `metadata.tenant` is `system`. A target's verified tenant appears only in its
  typed `target_object` reference. The untrusted request value is not copied.
- Records use only the `AuditRecord` fields in design §4.2. No raw request or
  response, credential value, raw payload, or free-text error is emitted.
- `action` is the full RPC method name. When a target is known, the matching
  typed `target_object` reference is set with verified identifying
  information.
- The credential-access case records the approved action/target without the
  credential value. Its concrete method remains an implementation prerequisite.

### TC-CAP-03: Request/response correlation, outcome, and stream completion

- **Requirements / interfaces:** FR-1, FR-3; IC-2, IC-3.
- **Owner / tier:** Fulfillment DEV; Unit.
- **Priority:** high.
- **Automation:** automated.

**Preconditions:** The interceptor test harness records enqueue attempts and
controls unary and streaming handler outcomes. It can set a stable receipt time
and completion time.

**Steps:**

1. Exercise a successful mutation, a successful read selected by policy, an
   authentication failure, an authorization denial, a validation failure, and
   a handler failure.
2. Exercise a selected stream with several messages, then complete it once
   successfully and once with failure/cancellation observed by the handler.
3. Inspect IDs, timestamps, actor/tenant attribution, and outcomes in the
   resulting enqueue attempts.

**Expected results:**

- Each selected call has distinct event `id` values for request and response
  records and one shared `request_id`. IDs are assigned before enqueueing and
  remain unchanged across publication retries.
- The request record has `outcome="PENDING"`; the response record uses the
  canonical final gRPC status name, such as `OK` or `PERMISSION_DENIED`.
  Outcomes are strings; there is no `operation_id`, `event_type`, or
  `metadata.status_code` in this design's record contract.
- Receipt and completion timestamps correspond to call entry and final RPC
  completion. Authentication failures omit actor and use the `system` record
  tenant. Authorization denials retain the authenticated actor and its
  verified tenant when available.
- A selected stream produces one request and one response record per RPC, not
  per message. No response record is attempted while the handler is still
  running.
- These are capture/enqueue assertions; they do not require Kafka
  acknowledgment before the API returns.

### TC-CONTRACT-01: Producer and consumer share the AuditRecord contract

- **Requirements / interfaces:** FR-3, FR-4, NFR-1; IC-1, IC-2.
- **Owner / tier:** Fulfillment DEV; Contract.
- **Priority:** high.
- **Automation:** automated.

**Preconditions:** The shared generated Protobuf type, audit producer
serialization, and consumer decoder are available to the test. The test runs
from `fulfillment-service/`.

**Steps:**

1. Build an `AuditRecord` with each optional field present, serialize it using
   the producer's binary Protobuf path, and decode it using the consumer's
   decoder.
2. Repeat with optional fields absent, including `actor` and target references;
   verify that record ownership still uses the required `metadata.tenant`
   value.
3. Inspect the generated public `AuditRecords` service and HTTP mapping.

**Expected results:**

- Producer and consumer preserve every field and the meaning of absent
  optional values across binary Protobuf serialization.
- The record contract contains the fields in design §4.2; it has no
  `operation_id`, `event_type`, or `metadata.status_code`.
- The public API exposes `AuditRecords.List` and
  `GET /api/fulfillment/v1/audit_records`; it exposes no create, update, or
  delete RPC method or HTTP route.
- Any later schema change must preserve compatibility with messages that
  remain in Kafka. This design defines no schema registry or schema-version
  field, so a historical-version fixture is not required by this case yet.

### TC-PUB-01: Asynchronous publication is bounded and fail-open

- **Requirements / interfaces:** NFR-2; IC-3.
- **Owner / tier:** Fulfillment DEV; Unit.
- **Priority:** high.
- **Automation:** automated.

**Preconditions:** A controllable publisher can delay or reject Kafka
acknowledgments, exhaust bounded retries, fill the bounded queue, and record
drop/failure signals. The test can observe the ordinary API result independently
of audit delivery.

**Steps:**

1. Hold the Kafka acknowledgment while making an ordinary selected API call;
   verify the API result is available before releasing the acknowledgment.
2. Reject publication until bounded retries are exhausted and make another
   call.
3. Fill the publisher queue and attempt another call.
4. Request publisher shutdown with records queued or awaiting acknowledgment;
   exercise the configured bounded drain through the publisher lifecycle
   harness.

**Expected results:**

- API responses do not wait for Kafka acknowledgment or retry completion.
- When acknowledgment is held, the API result is available before it is
  released. This is an ordering assertion, not a latency SLO.
- Queue saturation, publication failure, and shutdown can lose audit records,
  but do not change the API result.
- Failures and drops are observable. No test assumes a numeric queue capacity,
  retry count, backoff, timeout, or guaranteed drain; those are
  implementation-defined defaults and must be recorded in the test fixture.
- A request record may be present without its response record after a failure
  or shutdown. The plan makes no completeness guarantee beyond the design.

### TC-PUB-02: Real Kafka failures do not change Fulfillment results

- **Requirements / interfaces:** NFR-2; IC-3, IC-5.
- **Owner / tier:** Fulfillment DEV; component integration.
- **Priority:** high.
- **Automation:** automated.

**Preconditions:** A deployed Fulfillment API and real Kafka broker are
available. A test fault injector can independently delay and deny audit-topic
acknowledgments without replacing the broker or EventPublisher path. The
audit-specific test is proposed for `fulfillment-service/it/`.

**Steps:**

1. Hold an audit-topic acknowledgment, make a selected API call, and verify the
   ordinary API result before releasing the acknowledgment.
2. Deny audit publication through the configured bounded retry window, make a
   resource mutation, then inspect the API result and drop/failure signals.

**Expected results:**

- A held or denied Kafka acknowledgment does not change the API result or
  delay completion until acknowledgment.
- A committed mutation may have missing audit records; failed publication is
  observable. The test does not claim guaranteed capture or a numeric latency
  bound.
- Kafka is real. Fault injection controls only the broker/network failure; no
  provider reconciliation is run.

### TC-KAFKA-01: Topic creation, routing, and publisher/consumer access

- **Requirements / interfaces:** NFR-3; IC-5.
- **Owner / tier:** Fulfillment DEV; component integration.
- **Priority:** high.
- **Automation:** automated.

**Preconditions:** A disposable Kafka broker supports Admin API topic checks,
TLS, SCRAM-SHA-512, and identity/ACL assertions. Test records include verified
actor-tenant and `system` ownership cases, plus targets whose tenant differs
from the record owner.

**Steps:**

1. Hold the Kafka Admin API topic check/create operation while making a
   tenant's first selected API call; verify the API result before releasing the
   topic operation. Then inspect topic existence and routing.
2. Publish a record owned by `system` because the actor tenant is unknown or
   authentication failed. Publish a record whose target belongs to a different
   tenant from the record owner.
3. Attempt producer and consumer operations with the configured runtime
   identities and an unrelated identity.

**Expected results:**

- Records route by `metadata.tenant`: verified actor-tenant records use
  `osac.audit.<tenant-id>`; records owned by `system` use
  `osac.audit.system`. A target object's tenant does not affect topic routing.
- Before a tenant's first publication, the publisher checks for and creates
  its topic through Kafka Admin API. Topic setup does not delay the API request.
- The Fulfillment publisher has write access to audit topics; the consumer has
  read access to the audit topic patterns and its consumer group. Tenant
  workloads and API clients have no Kafka access. Bundled Kafka uses TLS and
  SCRAM-SHA-512; external deployments require equivalent encrypted
  authentication and access controls.
- Topic names and producer/consumer permissions follow the current design;
  tenant-onboarding topic provisioning and an `osac.audit.unattributed` topic
  are not assumed.

### TC-CONS-01: Consumer validation, idempotence, and offset recovery

- **Requirements / interfaces:** NFR-2; IC-2, IC-4.
- **Owner / tier:** Fulfillment DEV; component integration.
- **Priority:** high.
- **Automation:** automated.

**Preconditions:** A disposable real Kafka broker, PostgreSQL database, and
audit consumer are available. The harness can inspect offsets and arrange
failures before database commit and after database commit but before offset
commit.

**Steps:**

1. Publish valid records for two tenant topics and the `system` topic; verify
   persistence. Include a record whose target tenant differs from
   `metadata.tenant`. Poll every 2 seconds for up to 60 seconds after
   publication.
2. Replay a previously inserted event ID.
3. Inject malformed or invalid records, including a record whose
   `metadata.tenant` does not match its topic, followed by a valid record on
   the same topic.
4. Fail database insertion, then restore it. Separately terminate the consumer
   before database commit and after commit but before offset commit. After each
   restart, poll every 2 seconds for up to 60 seconds for the expected row and
   offset advancement.
5. Pause processing for one tenant topic while publishing to another tenant's
   topic.

**Expected results:**

- The consumer stores valid records and deduplicates by event `id`; replay does
  not create or alter a second row.
- `metadata.tenant` must match the topic suffix, including `system` for
  system-owned records. A target reference may name a different tenant and
  does not change the required topic. Topic/record-owner mismatches are
  rejected and reported; invalid records do not prevent later valid records
  from being processed.
- The consumer commits an offset only after a row insert or duplicate no-op
  succeeds. Database failure and a crash before commit leave the message
  eligible for replay. A crash after database commit but before offset commit
  redelivers without duplicating the row.
  - A stalled tenant topic does not block offset progress for another tenant
  topic. This does not claim isolation of shared Kafka broker, consumer, or
  database capacity. Polling limits are test bounds, not product recovery SLOs.

### TC-API-01: Query filters, ordering, pagination, and input validation

- **Requirements / interfaces:** FR-4; IC-1.
- **Owner / tier:** Fulfillment DEV; component integration.
- **Priority:** high.
- **Automation:** automated.

**Preconditions:** The audit table contains rows that differ by tenant, actor,
action, object type/ID, outcome, request ID, and event timestamp. Fixtures
include equal timestamps and enough rows to test page boundaries.

**Steps:**

1. Query through gRPC `AuditRecords.List` using individual and combined
   supported filters.
2. Repeat representative queries through
   `GET /api/fulfillment/v1/audit_records` using HTTP+JSON/ProtoJSON values.
3. Test omitted offset/limit, negative offset, zero limit, negative limit, a
   limit above 1000, and an invalid time range.
4. Page through matching rows with equal timestamps, checking only the
   ordering guaranteed by the standard Fulfillment List API.
5. Query with an outcome string absent from the fixtures.

**Expected results:**

- The API exposes List only at the design's gRPC method and HTTP route. Filters
  include `from_time`, `to_time`, `actor`, `action`, and CEL expressions on
  fields in the `target_object` oneof (for example, `has(this.cluster)`),
  `outcome`, `request_id`, provider-only `tenant_id`, `offset`, and `limit`.
  There is no `operation_id` filter.
- String filters match exactly. Outcomes are strings, not a required enum
  vocabulary. gRPC and HTTP+JSON return equivalent matching records and page
  shape. An unknown outcome string returns no matching rows and is not rejected
  as an invalid enum.
- Omitted offset defaults to zero; omitted limit defaults to 100. Negative
  offset is treated as zero. Limit zero returns `size=0` and the filtered
  `total` count without items; negative limit
  returns `InvalidArgument` / HTTP 400; limits above 1000 are capped at 1000.
- Assert only time-range validation behavior specified by the implemented
  standard Fulfillment filter/API contract. The design does not define
  endpoint inclusivity or whether equal endpoints are invalid; do not invent
  expectations for those details.
- Ordering follows the standard Fulfillment List API; this design does not
  define a new ordering contract. `size` is the page size and `total` is the
  matching count before pagination but after authorization scope.
- Verify query behavior against implemented storage/index choices; this
  design does not prescribe a specific audit-table index set.

### TC-AUTH-01: Query authorization and tenant scope

- **Requirements / interfaces:** FR-5; IC-1, IC-4.
- **Owner / tier:** Fulfillment DEV; component integration.
- **Priority:** high.
- **Automation:** automated.

**Preconditions:** Fixtures include records owned by tenant A, tenant B, and
`system`, including a Cloud Provider Admin action targeting tenant A. The
fixtures distinguish `metadata.tenant` (record owner/visibility) from
`target_object.tenant` (affected-object ownership). Authenticated principals
are available for Cloud Provider Admin, Tenant Admin, Cloud Infrastructure
Admin, and Tenant User.

**Steps:**

1. Query globally and by tenant as a principal authorized for platform scope.
2. Query as a principal authorized for tenant scope for tenant A, with and
   without filters and pagination; attempt to
   set `tenant_id`, including tenant A's own ID and tenant B's ID.
3. Try to read `system`-owned rows as Tenant Admin A.
4. Attempt queries as Cloud Infrastructure Admin and Tenant User.
5. Create request/response pairs whose records have different verified tenant
   attribution, then query one side by its `request_id`.

**Expected results:**

- A principal authorized for platform scope can query all records, including
  `system`-owned rows, or restrict results to one tenant.
- A caller authorized for tenant scope sees only records owned by their
  authenticated organization, including Cloud Provider Admin actions whose
  record owner is that tenant. A tenant-scoped caller cannot set `tenant_id`,
  even to their own tenant.
- The tenant-scoped principal cannot see `system`-owned rows, including records
  whose target belongs to tenant A. The persona-to-scope grants are not defined
  by this design; Cloud Infrastructure Admins and Tenant Users without the
  List permission are denied. Use Fulfillment's established authorization
  error behavior; this design does not specify a new status code for these
  denials.
- Tenant scope is applied to `metadata.tenant` before filters, counts, and
  pagination. `target_object.tenant` and a shared `request_id` do not expand
  visibility to records outside the caller's tenant scope.

### TC-AUDIT-01: Audit queries are themselves captured

- **Requirements / interfaces:** FR-6; IC-1, IC-3, IC-4.
- **Owner / tier:** Fulfillment DEV; component integration.
- **Priority:** high.
- **Automation:** automated.

**Preconditions:** Authenticated principals with platform and tenant List
scopes can query through the public API. Kafka publication and ingestion can be
observed without using repeated audit queries as the only observation
mechanism.

**Steps:**

1. Each principal makes one successful audit query.
2. Make a denied audit query and an invalid audit query.
3. Inspect Kafka or the audit table after asynchronous publication/ingestion.

**Expected results:**

- The query RPC is audited under the ordinary capture policy, using only the
  defined audit fields. The query filter payload is not stored.
- A successful `AuditRecords.List` call is on the sensitive-GET allowlist and
  produces request/response enqueue attempts; it is an explicit exception to
  the rule for ordinary successful GET calls.
- Successful, denied, and invalid query attempts are captured according to
  their RPC method classification and final gRPC result.
- Query audit records may appear only in a later query or may be absent if
  enqueue/publication fails. The test allows for asynchronous delivery and
  best-effort loss; it does not require the originating query to see its own
  records.
- Test polling does not use unbounded query loops that create audit events.
  Prefer Kafka/database observation. If polling is needed, poll every 2 seconds
  for up to 60 seconds after Kafka acceptance and account for the polling
  queries' own audit events; this is a test bound, not an ingestion SLO.

### TC-SEC-01: Credential values and raw payloads are excluded

- **Requirements / interfaces:** FR-7; IC-2, IC-3.
- **Owner / tier:** Fulfillment DEV; component integration.
- **Priority:** high.
- **Automation:** automated.

**Preconditions:** A supported API operation can carry a test-only credential
sentinel. A credential-access RPC is identified by the reviewed sensitive-GET
allowlist.

**Steps:**

1. Perform the credential-bearing operation and inspect request/response audit
   messages, stored rows, and public query results.
2. Access a credential through the allowlisted API method and inspect the
   emitted records.

**Expected results:**

- The sentinel, request/response body, raw payload, and free-text error appear
  nowhere in audit records or the public query result.
- The credential-access call is recorded by its approved method/action and
  target fields, with its final outcome and authenticated actor when present;
  the credential value is never stored.
- EventPublisher's separate resource-event redaction is not expanded into an
  audit-event contract by this test.
- The concrete credential-access method and its action/target mapping must be
  reviewed before this case is execution-ready.

### TC-APPEND-01: Runtime database roles enforce append-only storage

- **Requirements / interfaces:** NFR-1; IC-4, IC-5.
- **Owner / tier:** Fulfillment DEV; component integration.
- **Priority:** high.
- **Automation:** automated.

**Preconditions:** A disposable PostgreSQL database has the migration role,
Fulfillment API role, and audit-consumer role configured by the audit migration.

**Steps:**

1. Attempt insert/update/delete with the API database role.
2. Attempt update/delete with the consumer role and schema changes with either
   runtime role.
3. Verify the consumer can insert and the API can select audit rows.

**Expected results:**

- The API role can read audit rows but cannot insert, update, or delete them.
  The consumer role can insert but cannot update or delete. Neither runtime
  role can perform migrations; schema changes use the migration role.
- Rejected operations leave stored records unchanged.

### TC-OBS-01: Delivery and query diagnostics avoid attribution values

- **Requirements / interfaces:** NFR-2; IC-3, IC-4.
- **Owner / tier:** Fulfillment DEV; Unit.
- **Priority:** high.
- **Automation:** automated.

**Preconditions:** Recording log and metric sinks are available. Fixtures use
distinct tenant, actor, resource, credential, and free-text-error markers and
can induce queue saturation, acknowledgment timeout, exhausted retries,
invalid records, insert failure, consumer lag, and query unavailability.

**Steps:** Exercise healthy and failing paths, then inspect emitted signals,
logs, and metric labels for the fixture markers.

**Expected results:**

- Signals cover publisher queue depth/full state, Kafka publication latency and
  acknowledgment timeouts, publication failures/drops, consumer lag per topic,
  invalid records, insert failures, and query availability.
- Logs and metric labels contain no tenant, actor, resource, or credential
  values. No numeric alert threshold or product SLO is asserted.

### TC-RET-01: Stored audit rows survive restart without a retention job

- **Requirements / interfaces:** NFR-4; IC-4.
- **Owner / tier:** Fulfillment DEV; component integration.
- **Priority:** high.
- **Automation:** automated.

**Preconditions:** A record is stored in PostgreSQL and the disposable test
environment can restart Fulfillment, the consumer, and PostgreSQL.

**Steps:** Restart the services/database, query the stored record, and inspect
migrations and scheduled jobs for audit-row deletion or TTL configuration.

**Expected results:**

- The same row ID and fields remain queryable after restart.
- This milestone has no PostgreSQL audit-row deletion/retention job. Kafka's
  finite retention is transport retention and does not imply PostgreSQL row
  deletion.
- If Kafka retention expires before an event is inserted into PostgreSQL, the
  design does not promise recovery from Kafka.

### TC-DEPLOY-01: Deployment wiring and jurisdiction requirements

- **Requirements / interfaces:** NFR-3; IC-5.
- **Owner / tier:** Installer DEV; Contract.
- **Priority:** high.
- **Automation:** manual.

**Preconditions:** The implementation identifies the deployment manifests and
runtime identities for Kafka, the Fulfillment publisher, the audit consumer,
PostgreSQL, and database backups. Bundled and external service configurations
are available if both are supported. Working directory is N/A: this procedure
requires evidence from the target deployment and its operator, not a local
repository command.

**Manual procedure:**

1. Inspect rendered/runtime configuration for endpoints, TLS and SCRAM
   authentication, publisher and consumer identities/ACLs, database roles,
   topic patterns, and backup coverage.
2. Verify bundled service endpoints are deployment-local and identify how an
   operator verifies jurisdiction for external Kafka, PostgreSQL, and backups.

**Expected results:**

- Runtime identities and permissions match design §§4.2 and 4.5; audit data is
  stored in Fulfillment PostgreSQL for this milestone.
- Bundled Kafka uses TLS and SCRAM-SHA-512. External Kafka uses equivalent
  encrypted authentication and access controls.
- Configuration and operator evidence establish the deployment-jurisdiction
  prerequisite. Endpoint URLs or rendered Helm alone are not proof of physical
  location.
- The audit table is included in the configured database backup/replication
  coverage.
- No Keycloak listener, Enclave plugin, Wizard control, tenant-onboarding
  topic provisioning, or audit disable/re-enable control is required by the
  current design.

## Planning evidence and execution boundaries

The repository's canonical tiers and work ownership follow
[Integration testing](https://github.com/osac-project/osac/blob/main/docs/INTEGRATION-TESTING.md#planning-evidence). Unit,
component-integration, and Contract tests belong to the owning DEV work. No QE
E2E case is assigned: this increment has no UI, provider-provisioning journey,
or cross-component lifecycle outcome. The deployed acceptance boundary is the
Fulfillment API, its Kafka publisher/consumer, and PostgreSQL.

Each matrix row references cases whose `Preconditions` sections identify its
environment and fixtures. Every row is planned and not run; a proposed path or
existing runner does not establish execution readiness for the new audit case.

| Behavior / references / cases | Owner and canonical tier | Suite, command/procedure, and working directory | Real boundary; simulated or omitted dependencies | Execution status | Gap / follow-up |
|---|---|---|---|---|
| RPC classification, attribution, request/response construction (FR-1/2/3; IC-2/3; TC-CAP-01/02/03) | Fulfillment DEV; Unit | Proposed `fulfillment-service/internal/servers/audit_interceptor_test.go`; `ginkgo run --timeout 10m internal/servers`, working directory `fulfillment-service/` | Real interceptor and record-building code; controlled identity, method registry, handler, and recording publisher. No Kafka, database, or provider. | Not run; planned. | Proposed tests and action/target mappings are not implemented. No follow-up Jira ticket is identified in this plan. |
| Producer/consumer Protobuf contract and public API descriptors (FR-3/4; IC-1/2; TC-CONTRACT-01) | Fulfillment DEV; Contract | Proposed `fulfillment-service/internal/servers/audit_contract_test.go`; `ginkgo run --timeout 10m internal/servers`, working directory `fulfillment-service/`. `make lint` / `make generate` from `proto/` are supplemental schema checks, not the behavioral contract test. | Real generated Protobuf types, producer serializer, consumer decoder, and public descriptors; no live Kafka, PostgreSQL, or provider. | Not run; planned. | Proposed test file/contract fixture do not exist. No follow-up Jira ticket is identified in this plan. |
| Publisher queue saturation, retry, shutdown, and API result (NFR-2; IC-3; TC-PUB-01, TC-OBS-01) | Fulfillment DEV; Unit | Proposed `fulfillment-service/internal/servers/audit_publisher_test.go`; `ginkgo run --timeout 10m internal/servers`, working directory `fulfillment-service/` | Real queue and signal code; controlled publisher acknowledgments, clock, and API handler. No live Kafka, database, or provider. | Not run; planned. | Queue/retry settings and tests are not implemented. No follow-up Jira ticket is identified in this plan; use configured implementation values, not invented product guarantees. |
| Fail-open publication against Kafka (NFR-2; IC-3/5; TC-PUB-02) | Fulfillment DEV; component integration | Proposed `fulfillment-service/it/it_audit_delivery_test.go`; `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`, working directory `fulfillment-service/` | Real deployed Fulfillment API and Kafka acknowledgment path; test fault injector delays/denies broker acknowledgments. EventPublisher remains real and independent. No provider. | Not run; planned. | Audit fault injector and suite selection are unresolved. No follow-up Jira ticket is identified in this plan. |
| Topic creation, routing, and Kafka ACLs (NFR-3; IC-5; TC-KAFKA-01) | Fulfillment DEV; component integration | Proposed `fulfillment-service/it/it_audit_kafka_test.go`; `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`; cwd `fulfillment-service/` | Real Kafka Admin API, topics, TLS/SCRAM authentication, publisher and consumer identities/ACLs, and deployed Fulfillment publisher. No PostgreSQL or provider. | Not run; planned. | Kafka audit fixture and test identity setup are unresolved. No follow-up Jira ticket is identified in this plan. |
| Consumer validation, database insert, deduplication, offset recovery, and topic progress (NFR-2; IC-2/4; TC-CONS-01) | Fulfillment DEV; component integration | Proposed `fulfillment-service/it/it_audit_consumer_test.go`; `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`; cwd `fulfillment-service/` | Real Kafka group offsets, consumer process, and PostgreSQL transactions; deterministic crash barriers and known event IDs. No provider. | Not run; planned. | Consumer restart/crash harness is unresolved. No follow-up Jira ticket is identified in this plan. Mocked commit ordering does not satisfy this boundary. |
| Query filtering, pagination, authorization, and audit-of-audit (FR-4/5/6; IC-1/3/4; TC-API-01, TC-AUTH-01, TC-AUDIT-01) | Fulfillment DEV; component integration | Proposed `fulfillment-service/it/it_audit_api_test.go`; `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`; cwd `fulfillment-service/` | Real deployed public gRPC/HTTP API, PostgreSQL, authenticated test identities with explicit List permission scopes, Kafka publisher/consumer for audit-of-audit. No provider. | Not run; planned. | API fixture/suite is not present. No follow-up Jira ticket is identified in this plan. Time-range endpoint semantics remain open; do not assert unspecified inclusivity or equal-endpoint behavior. |
| Credential redaction and approved access record (FR-7; IC-2/3; TC-SEC-01) | Fulfillment DEV; component integration | Proposed `fulfillment-service/it/it_audit_api_test.go`; `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`; cwd `fulfillment-service/` | Real public API, Kafka, consumer, PostgreSQL, and query path; test-only credential sentinel. No provider. | Not run; planned. | Credential method/action/target mapping and fixture are unresolved. No follow-up Jira ticket is identified in this plan. |
| Append-only runtime database privileges (NFR-1; IC-4/5; TC-APPEND-01) | Fulfillment DEV; component integration | Proposed `fulfillment-service/it/it_audit_storage_test.go`; `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`; cwd `fulfillment-service/` | Disposable PostgreSQL with API, consumer, and migration roles configured by the audit migration. No Kafka or provider for SQL privilege assertions. | Not run; planned. | Role fixture and executable case are unresolved. No follow-up Jira ticket is identified in this plan. |
| Row retention across restart (NFR-4; IC-4; TC-RET-01) | Fulfillment DEV; component integration | Proposed case in `fulfillment-service/it/it_audit_storage_test.go`; `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`; cwd `fulfillment-service/` | Disposable database with a stored audit row; ability to restart Fulfillment, consumer, and PostgreSQL. | Not run; planned. | Audit storage/restart fixture is not present. No follow-up Jira ticket is identified in this plan. |
| Deployment jurisdiction and backup/replication evidence (NFR-3/4; IC-5; TC-DEPLOY-01) | Installer DEV; Contract | Manual review of target deployment configuration and operator evidence; working directory N/A because the boundary is deployment-specific and cannot be established by a local command. | Actual endpoint placement, deployment jurisdiction, and backup/replication evidence; no physical-location claim from URLs/rendered output alone. | Not run; planned manual review. | Exact deployment files and evidence procedure are unresolved. No follow-up Jira ticket is identified in this plan. |

## Open planning decisions

Resolve these items before claiming the affected cases are execution-ready:

1. Identify the production RPC classification registry, sensitive GET
   allowlist, and credential-access method/action/target mapping.
2. Define the invalid-time-range rule and any endpoint inclusivity for
   `from_time` / `to_time` if this milestone requires behavior beyond the
   standard Fulfillment List/filter contract; the design currently does not
   specify these details.
3. Record implemented queue capacity, retry count/backoff, acknowledgment
   timeout, and shutdown drain bound in test fixtures. These are not product
   guarantees unless separately specified.
4. Identify the deployment/test harness for real Kafka topics, identities,
   consumer offsets, PostgreSQL roles, and backup coverage. Proposed tests need
   named executable commands before they are execution-ready.
5. Identify how operators verify jurisdiction for externally managed Kafka,
   PostgreSQL, and backups. Rendered endpoints alone are insufficient evidence.
6. Define how future Protobuf schema changes are tested for compatibility with
   records that remain in Kafka; this design defines no schema registry or
   version field.

## Summary

| Measure | Count / status |
|---|---:|
| Planned test cases | 16 |
| Design requirement labels mapped | 11 / 11 |
| Interface changes mapped | 5 / 5 |
| Executed in this design phase | 0 |
| Cases with implementation-specific or harness gaps | See planning evidence and open decisions |
