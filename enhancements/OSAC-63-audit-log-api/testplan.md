# Testplan — OSAC-63

## Overview

- **Feature:** OSAC-63 — Activity and Audit Log API
- **Traceability labels:** `FR-1`–`FR-8` and `NFR-1`–`NFR-4` map to current-increment behavior in the PRD, as listed in the [design](design.md). The PRD itself has no FR/NFR IDs.
- **Total planned test cases:** 33 (30 original; 3 decomposition addendum cases)
- **Traceability labels with planned cases:** 12 of 12; FR-1, FR-3, FR-4, FR-8, NFR-2, and NFR-3 have unresolved mapping, fixture, or deployment-prerequisite gaps below. Planned coverage is not execution readiness.
- **Interface changes with planned cases:** 7 of 7.
- **Execution status:** This is a design-stage plan. No new suite or implementation has run.

Fulfillment saves request receipt time and method classification at gRPC entry
and assigns an `operation_id` when the call is selected for capture.
For methods selected by classification, after authentication and before
authorization or business work, it publishes a request record with the verified
actor and waits for Kafka acknowledgment or
the bounded timeout. If validation or authentication stops the call first, it
publishes the request record when the error returns, with no actor unless
authentication succeeded. Successful ordinary reads publish neither record;
authentication failures or authorization denials on those reads select the
call for capture and publish the request before the response when the error
returns, preserving the original receipt time. For selected calls, it publishes a
response record after the final RPC and transaction result, then waits for
acknowledgment or timeout before returning. The request record uses
`outcome=PENDING`; the response record uses the canonical gRPC status code
name, such as `OK` or `PERMISSION_DENIED`. A lifecycle record uses the exact
resource state value from `status.state`. The two
records have distinct row IDs and share one `operation_id`;
there is no `request_stage` field.
Every accepted feedback update with a resolved field mapping adds a separate
lifecycle record, with its own action and outcome, including ordinary and
repeated updates. Exceptions remain open as listed in design §7.2.
A feedback call rejected before its update is accepted has only API capture
attempts. Current feedback does not carry the original Create operation ID,
so the request, response, and lifecycle records for an accepted update with a
resolved mapping share a new server-generated `operation_id` for the feedback
call. This groups those three records without linking them to the original Create;
`object_id` alone does not establish causation. Each independent Keycloak
event receives its own new `operation_id`. Failed logins always have
`tenant_id=NULL` and provider-only visibility. Set `actor` to the targeted
account when the Keycloak event includes the resolved account; otherwise leave
it unset. Never infer a tenant or actor from the submitted login identifier. The
required `event_type` values are `api_request`, `api_response`,
`resource_lifecycle`, and `authentication`.
Every stored record has a non-null `operation_id`. Only API call response
records have `metadata.status_code`.
Optional metadata contains only allowlisted details. If a response record is
missing, the audit trail cannot establish the call's final outcome or whether
it is still running.

The `outcome` field and filter are strings, not an `AuditOutcome` enum. Use
`PENDING` for API requests, canonical gRPC status code names for API responses,
the exact source `status.state` value for lifecycle records, and the source
value for authentication records. `source` and `event_type` are protobuf enums;
HTTP+JSON represents `outcome` as the same exact string.

Canonical action identifiers and selected Keycloak event/action/outcome mappings
must be reviewed during implementation under design §2.4.1. Action literals in
this plan, including `clusters.create`, and Keycloak event examples such as
`LOGIN`, `LOGIN_ERROR`, `CODE_TO_TOKEN`, `REFRESH_TOKEN`, `LOGOUT`, and
`USER_SESSION_DELETED`, are proposed fixtures, not additional design contracts.
Bind action filters and expected values to the reviewed mappings before
execution. Preserve the specified login, token, session, and audit-query
behaviors rather than assuming these example names are mandatory.

For healthy-delivery assertions below, poll the audit query every 2 seconds
for up to 60 seconds after the source call; check Kafka acceptance separately
where relevant. This is a test timeout, not a product ingestion SLO. Identify
the target rows by supported action, object type/ID, actor, and time filters or by
database inspection; polling queries themselves create audit events.

## Test Cases

### FR-1: Fulfillment business API calls and identity activity

#### TC-FR1-01: Fulfillment calls and significant outcomes enter the audit history

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3/4 | critical | automated |

##### Preconditions

- A deployed Fulfillment API, audit activity topic, separate consumer, and PostgreSQL audit table are available. The feedback action/outcome mapping is defined for at least one tested resource.

##### Steps

1. Create, read, update, and delete tenant-scoped BareMetalInstance, Cluster, and ComputeInstance resources through the API; inspect their audit history as a provider and compare tenant-scoped queries.
2. Drive a documented completion or failure through the Fulfillment feedback API and query again. Inspect the operational tenant Event topic separately.

##### Expected Results

- With healthy audit delivery, each mutation has two call records with distinct IDs and one `operation_id`: `api_request` with `outcome=PENDING` and `api_response` with `outcome=OK` after commit. Successful ordinary reads produce no audit records; sensitive reads are tested separately under TC-FR8-02 and the reviewed classification registry.
- Every accepted feedback update for a resource with a resolved mapping has two API call records and a separate `resource_lifecycle` record with three distinct row IDs and one new `operation_id`, distinct from the original Create call's. The lifecycle row has the mapped action and exact source state outcome, object type, ID, and tenant. Tenant Events still reach operational consumers. Rows for tenant A do not appear in a tenant B query.

#### TC-FR1-02: Administrative mutation is classified without retaining a resource snapshot

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | high | automated |

##### Preconditions

- An authorized administrator and audit query principal exist; Tenant or RoleBinding mutation is available through Fulfillment.

##### Steps

1. Perform an authorized Tenant or RoleBinding mutation through Fulfillment.
2. Query by its action and time window or inspect the database, group rows by `operation_id`, and verify the response record's object ID.

##### Expected Results

- Two administrative API-call rows have distinct IDs and one `operation_id`; the response record names the canonical action, target type/ID, principal, tenant when applicable, and `outcome=OK` after commit.
- Neither row has a request body, response body, or serialized Tenant/RoleBinding payload.

#### TC-FR1-03: Method classification and capture exclusions apply across transports

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | critical | automated |

##### Preconditions

- A reviewed method registry identifies POST/PUT/PATCH/DELETE mappings, an ordinary GET, and a sensitive GET. A test gRPC service supplies an unmapped business RPC if no production method does. The server harness can inspect publication order and invoke authentication, authorization, and panic recovery through the real interceptor chain.

##### Steps

1. Exercise each mutating HTTP-method classification, the sensitive GET, and the unmapped RPC through native gRPC. Repeat a mapped call through HTTP+JSON.
2. Exercise an ordinary read successfully, without valid authentication, and with an authenticated caller denied authorization. Delay the rejection in the harness to distinguish receipt time from error-return time.
3. Trigger a recovered panic on a selected business RPC. Exercise health, reflection, transport probes, and a failure before the gRPC boundary.

##### Expected Results

- Mutating mappings, sensitive reads, and unmapped business RPCs are captured, including native gRPC calls. Each selected call attempts one request/response pair; HTTP+JSON routing through gRPC does not double-capture it.
- The successful ordinary read publishes nothing. Each rejected ordinary read publishes its request before its response when the error returns, using the original receipt time. Authentication failures have no actor or token-derived identity; authorization denials retain the authenticated actor. Request outcomes are `PENDING`; response outcomes are the final gRPC status code names.
- A recovered panic produces a `PENDING` request and a response with the recovered final gRPC status code. Excluded probes and pre-boundary failures produce no audit publications.

#### TC-FR1-04: Streaming RPCs produce one pair at RPC completion

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | high | automated |

##### Preconditions

- The server harness exposes a selected streaming business RPC through the real audit interceptor chain and a recording publisher. Completion and final status can be controlled independently of message delivery.

##### Steps

1. Authenticate a stream, send multiple messages, and hold the handler open before completing successfully.
2. Repeat with a handler failure or client cancellation observed by the handler.

##### Expected Results

- Each stream has one `PENDING` request record, published after authentication and before authorization/business work, and no response record while its handler remains open. Messages do not create additional pairs.
- Handler completion creates one response record with the final RPC outcome/status and completion timestamp. Its ID differs from the request ID and its `operation_id` matches. Failure/cancellation does not change this one-pair rule.

### FR-2: Authenticated actor on user-initiated actions

#### TC-FR2-01: A user-initiated API call retains the initiating user

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | critical | automated |

##### Preconditions

- A tenant user can mutate a resource through Fulfillment; the authenticated actor differs from the resource creator.

##### Steps

1. The user updates a resource; inspect the resulting API audit records as a provider or in the database.
2. As a provider, query the call by `operation_id` with and without the user's exact actor filter.

##### Expected Results

- Both request and response records identify the authenticated updater and canonical action; the provider's actor-filtered query returns both.
- A resource creator value different from the updater does not replace the updater as actor. Under healthy delivery the call has two records with distinct IDs and one `operation_id`; the request record leaves an unverified target null.

#### TC-FR2-02: Actorless lifecycle outcome remains visible

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | critical | automated |

##### Preconditions

- A feedback API call reports a lifecycle outcome without the initiating user's identity.

##### Steps

1. Ingest the feedback call and its lifecycle record, then query by object ID and lifecycle action with no actor filter.
2. Repeat with an actor filter set to a real user.

##### Expected Results

- The first query returns the lifecycle row without the initiating user as actor; the second excludes that row. The feedback call's request, response, and lifecycle records share a new `operation_id` without claiming a link to the original user operation.

### FR-3: Request acceptance and lifecycle feedback outcomes

#### TC-FR3-01: Writes retain their final outcome and status code

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | critical | automated |

##### Preconditions

- A desired-state Create method is available; the test can induce a validation rejection and an exception before commit.

##### Steps

1. Submit a valid Create request, inspect its audit-topic messages, then poll as a provider for its linked request and response records.
2. Submit a rejected Create request and a Create request that fails before commit; query as a provider by action and outcome.
3. Trigger multiple resource Events for the successful call and query again.

##### Expected Results

- After commit and ingestion, the successful Create has a request record published and acknowledged after authentication but before authorization or business work, timestamped at receipt with the authenticated actor and `outcome=PENDING`. Its response record has the same actor and `outcome=OK` after commit, and is acknowledged before the API response returns when Kafka is healthy. Their IDs differ and `operation_id` matches. Only the response record has `metadata.status_code=OK`; it also has the object ID and tenant from the committed object. Success means request acceptance, not completed provisioning; there is no premature lifecycle record.
- Each validation or transaction failure has a request record with `outcome=PENDING` and a response record whose `outcome` is the final gRPC status code name, also recorded in `metadata.status_code`. A validation failure before authentication has no actor; a transaction failure retains the verified actor on both records. No successful response record is stored. Unverified target fields remain null.
- The resource Events in step 3 produce no additional audit rows.

#### TC-FR3-02: API response and lifecycle outcome differ

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | critical | automated |

##### Preconditions

- The Clusters feedback API has both mapped fields from design §2.2.3 and fixtures for READY and FAILED. One accepted Cluster Update carries `status.state_transition_time` earlier than the feedback call's receipt time.

##### Steps

1. Submit accepted feedback updates with no documented application-state transition, a success transition, a terminal failure, and a repeated status update.
2. Query by object ID, lifecycle action, and `outcome`.
3. Submit a feedback call rejected before its update is accepted; inspect its linked API records and confirm no lifecycle record or persisted feedback update exists.

##### Expected Results

- Each accepted feedback call for a Cluster has an `api_request` record with `outcome=PENDING`, an `api_response` record with `outcome=OK` and `metadata.status_code=OK`, and a separate `resource_lifecycle` record. All three have distinct row IDs and share the feedback call's new `operation_id`. This does not link them to the original Create operation. The lifecycle `outcome` exactly matches `object.status.state` from that Update payload, and `event_timestamp` exactly matches its `object.status.state_transition_time`; lifecycle metadata has no fields. A feedback Update returning `OK` while reporting `CLUSTER_STATE_FAILED` therefore has a successful API response record and a lifecycle outcome of `CLUSTER_STATE_FAILED`.
- The delayed feedback call's request and response records use request receipt and final RPC times; its lifecycle record uses the earlier `object.status.state_transition_time` from the Update payload, not Fulfillment's receipt time.
- Ordinary and repeated feedback updates also have a lifecycle record, in addition to their linked request and response records.
- The rejected feedback call attempts only a `PENDING` API request and an API response whose outcome is the final gRPC status code name. It creates no lifecycle record; the recorded resource state remains unchanged.

### FR-4: Tenant-attributed Keycloak authentication events

#### TC-FR4-01: Login success is tenant-attributed; failure is provider-only

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5/6 | critical | automated |

##### Preconditions

- Real Keycloak 26.6.4 runs the listener; the audit activity topic and separate Fulfillment audit consumer deployment are available; a known user belongs to one OSAC organization.

##### Steps

1. Log in with the correct credential, then attempt a login for the same user with a wrong credential.
2. Query the organization's trail by actor and `LOGIN`/`LOGIN_ERROR` actions; query from another tenant and globally as a Cloud Provider Admin.

##### Expected Results

- The first tenant sees the `authentication` `LOGIN` row with `outcome=success`, the verified user actor, and its authenticated organization. Neither tenant sees the `LOGIN_ERROR` row. The Cloud Provider Admin sees both rows with distinct event IDs and operation IDs.
- The `LOGIN_ERROR` row has `outcome=failure` and `tenant_id=NULL`, even though the targeted account belongs to a known organization. Its actor is the targeted account when the Keycloak event includes the resolved account; otherwise actor is unset. Never derive tenant or actor from the submitted login string.
- Neither row contains the password or token value.
- The realm upgrade that installed the listener preserves the pre-existing user, organization, roles, and `jboss-logging` listener.

#### TC-FR4-02: Token and session operations are captured by selected types

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5/6 | high | automated |

##### Preconditions

- The same Keycloak user has a live session and can perform a refresh/code-to-token operation.

##### Steps

1. Exchange a code or refresh a token, then log out or end the session.
2. Query the tenant trail by the corresponding Keycloak action.

##### Expected Results

- A `CODE_TO_TOKEN` or `REFRESH_TOKEN` row and a `LOGOUT` or `USER_SESSION_DELETED` row appear with the same tenant and user actor. Each independent Keycloak event has a distinct row ID and its own non-null `operation_id`.
- Token contents and Keycloak `details` are absent from the audit-topic message and stored rows.

#### TC-FR4-03: Unresolved identity and invalid messages are not misattributed

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5/6 | high | automated |

##### Preconditions

- Keycloak produces a `LOGIN_ERROR` without a resolvable user ID; two tenant organizations have distinct members. The consumer harness can inject malformed binary protobuf and invalid envelope/record fixtures on one partition.

##### Steps

1. Trigger the error using an unknown identity string resembling a tenant email domain.
2. Query both tenant trails and inspect provider-visible records and the listener's safe diagnostics.
3. Replay the same audit-topic event ID to Fulfillment's consumer.
4. In separate runs, publish malformed protobuf, an unsupported schema version, unknown and required `UNSPECIFIED` enums, and missing/invalid required record fields (including event ID, operation UUID, occurrence time, and action). Follow each invalid message with a valid event on the same partition.

##### Expected Results

- Neither tenant trail receives the record; no tenant or actor is inferred from the unverified identity string.
- A Cloud Provider Admin query can retrieve one provider-only `LOGIN_ERROR` row with `tenant_id=NULL`, null actor, its own `operation_id`, and no guessed tenant.
- The replay creates no second row.
- Each invalid event creates no row and is reported without leaking record values; the following valid event is stored once. Unsupported versions and unknown or required `UNSPECIFIED` enum values are rejected.
- Authentication still returns its original failure response.

### FR-5: gRPC and HTTP+JSON query with filters and actorless records

#### TC-FR5-01: Exact filters, operation lookup, and half-open time range select records

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | critical | automated |

##### Preconditions

- The Fulfillment audit table contains call and lifecycle fixtures that differ by actor, action, type, ID, outcome, and timestamps at both time boundaries. One call pair shares `operation_id` but has distinct row IDs; its request record has a verified provider actor, `tenant_id=NULL`, and `outcome=PENDING`, while its response record has the same actor, belongs to tenant A, and has `outcome=OK`. A separate Cluster feedback fixture has request, response, and lifecycle records with one `operation_id` and distinct row IDs; its lifecycle outcome is `CLUSTER_STATE_FAILED`.

##### Steps

1. Call gRPC `AuditRecords.List` with all filters and `[from_time, to_time)`.
2. Remove one filter at a time and compare returned IDs.
3. Query the call pair by `operation_id` with no outcome filter, then with the exact string values `PENDING`, `OK`, and `CLUSTER_STATE_FAILED`, first as a Cloud Provider Admin and then as a tenant A Tenant Admin.
4. Query the feedback fixture by its `operation_id` with no outcome filter and with `CLUSTER_STATE_FAILED`; also query by object ID and lifecycle action.
5. Repeat representative exact-string outcome filters through HTTP+JSON and compare IDs and page shape with gRPC.

##### Expected Results

- The full-filter call returns only fixture IDs matching every specified field and timestamps at or after `from_time` and before `to_time`.
- Removing a filter can add only fixtures that differ on that field; `to_time` boundary records remain excluded.
- With an empty outcome filter, the provider retrieves both rows for the call pair's `operation_id`; the request record has `outcome=PENDING`. The Tenant Admin retrieves only the tenant-attributed response record. The provider-only request record remains hidden from the Tenant Admin. `outcome=PENDING` returns only the request record; `outcome=OK` returns only the response record; `outcome=CLUSTER_STATE_FAILED` returns neither call-pair row.
- The feedback `operation_id` lookup returns all three rows: the request and response records and the separate lifecycle row. Filtering that operation by `CLUSTER_STATE_FAILED`, or querying by object ID and lifecycle action, returns the lifecycle row. Its outcome is independent of the feedback call's successful response record. The feedback ID does not return the earlier Create rows.
- Both transports return the same scoped/filter-matching records and `size`, `total`, and `items` shape. An unset outcome applies no outcome restriction.

#### TC-FR5-02: HTTP offset/limit pagination and scoped totals

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | high | automated |

##### Preconditions

- 201 rows visible to the caller match `action=clusters.create`, including two with the same `event_timestamp`; all are durably ingested before paging begins.

##### Steps

1. With no matching inserts between requests, call `GET /api/audit/v1/records?action=clusters.create&offset=0&limit=100`, then repeat with `offset=100` and `offset=200`.
2. Insert and commit one newer matching record, then repeat the first-page and last-page requests.

##### Expected Results

- Before the insert, page `size` values are 100, 100, and 1; each response has `total=201`, and the pages contain each row once in `(event_timestamp DESC, id DESC)` order.
- After the insert, the first page starts with the new row, the last page has two rows, and both report `total=202`. Previously fetched offset pages are not a snapshot and may overlap later pages.

#### TC-FR5-03: Actorless outcomes match other filters

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | high | automated |

##### Preconditions

- An actorless Cluster lifecycle row has `outcome=CLUSTER_STATE_FAILED` and shares the feedback call's `operation_id` with its `outcome=PENDING` request record and `outcome=OK` response record.

##### Steps

1. Use gRPC `AuditRecords.List` to query by object ID, lifecycle action, and
   `outcome=CLUSTER_STATE_FAILED`, first without an actor filter, then with one.
   Repeat with `outcome=CLUSTER_STATE_READY` and no actor filter. Query the feedback action
   separately with `outcome=OK`.

##### Expected Results

- The first response includes the actorless lifecycle row; the actor-filtered and opposite-outcome responses exclude it. The feedback-action query returns the separate `OK` response record.

#### TC-FR5-04: Invalid query inputs have explicit errors

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | medium | automated |

##### Preconditions

- A valid audit query principal is authenticated, and 1,001 visible fixture rows match one action filter.

##### Steps

1. Call List with `from_time >= to_time`, an omitted `limit`, `limit=-1`, and `limit=0` in separate requests.
2. Query with an outcome string that matches no stored value.
3. With the matching action filter, call List using `offset=-1&limit=1001`.

##### Expected Results

- Each invalid request in step 1 returns gRPC `InvalidArgument` / HTTP 400 and no result items; its own audit trail still has a `PENDING` request record and a response record whose outcome is `INVALID_ARGUMENT`.
- Step 2 treats an unknown outcome as an exact string filter and returns no matching items without an error.
- Step 3 treats the offset as 0 and caps the limit at 1000, returning `size=1000` and `total=1001`.

### FR-6: Authorized tenant and provider scopes; denied queries

#### TC-FR6-01: Tenant Admin cannot widen organization scope

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | critical | automated |

##### Preconditions

- Tenant A and tenant B each have a `clusters.create` record; a Tenant Admin token belongs only to tenant A.

##### Steps

1. List with `action=clusters.create` and no `tenant_id`, then repeat with an offset past tenant A's last item.
2. Specify `tenant_id=tenant-b`, then `tenant_id=tenant-a`, in separate List requests.

##### Expected Results

- The item page contains only tenant A rows. Every response's `total` counts only tenant A matches, including the empty offset page.
- Both requests specifying `tenant_id` return `PermissionDenied` / HTTP 403 and no result items or counts. Only Cloud Provider Admins may set this filter, including when a Tenant Admin selects their own organization.

#### TC-FR6-02: Cloud Provider Admin uses global and per-tenant modes

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | critical | automated |

##### Preconditions

- A Cloud Provider Admin token and rows with `tenant_id` set to tenant A, tenant B, and `NULL` exist.

##### Steps

1. List without `tenant_id` and then list with `tenant_id=tenant-a`.

##### Expected Results

- The global response includes A, B, and provider-only rows; the tenant-filtered response includes only tenant A rows.

#### TC-FR6-03: Excluded personas and missing identity are denied

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | critical | automated |

##### Preconditions

- Cloud Infrastructure Admin, Tenant User, and unauthenticated clients are available.

##### Steps

1. Each client calls `AuditRecords.List`.

##### Expected Results

- The two authenticated excluded personas receive `PermissionDenied` / HTTP 403, and the unauthenticated call receives `Unauthenticated` / HTTP 401; all responses contain no records.
- Each denied call produces a request record with `outcome=PENDING` and a response record whose `outcome` is the canonical gRPC status code name also recorded in `metadata.status_code`. Authenticated denials retain the verified actor on both records and tenant when resolved. The unauthenticated call's records have no actor or inferred tenant; request records may lack other unverified attribution.

### FR-7: Audit access by every principal

#### TC-FR7-01: Allowed global and tenant queries create linked access records

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | critical | automated |

##### Preconditions

- Tenant Admin and Cloud Provider Admin tokens exist; the audit topic, consumer, and table are available.

##### Steps

1. Each principal performs one authorized query; the provider queries without a tenant filter.
2. As a provider, poll for the first queries' rows using the reviewed audit-query action mapping after their audit messages are accepted by Kafka; group each query's rows by `operation_id`.

##### Expected Results

- Exactly two rows with the mapped audit-query action per first query have distinct IDs and one `operation_id`: a request record with `outcome=PENDING` and a response record with `outcome=OK`. Both records have the authenticated principal. Both Tenant Admin query records have their authenticated organization's `tenant_id`; the provider's global-query records have `tenant_id=NULL`.
- Reading the audit table and ingesting those records do not create extra access rows for those first queries; polling queries have their own `operation_id` values.

#### TC-FR7-02: Denied and failed query attempts remain visible to provider

| Interface Change | Priority | Automation |
|---|---|---|
| IC-6 | high | automated |

##### Preconditions

- A Tenant User token and Cloud Provider Admin token exist.

##### Steps

1. Have the Tenant User attempt List and the provider submit `limit=-1`.
2. Query the audit trail as the provider by the reviewed audit-query action mapping.

##### Expected Results

- The provider sees each earlier query's linked request record with `outcome=PENDING` and response record whose outcome matches its canonical gRPC status code. One response has `PERMISSION_DENIED` for the Tenant User; the other has `INVALID_ARGUMENT` for the provider's limit. None contains the full filter payload.
- The Tenant User cannot query either row.

### FR-8: Credential contents exclusion and credential-access metadata

#### TC-FR8-01: Secret sentinel never enters operational Events or audit storage

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | critical | automated |

##### Preconditions

- A supported API mutation contains a test-only credential sentinel in a Secret or credential field; tenant Event, audit-topic, and PostgreSQL inspection are available.

##### Steps

1. Perform the API mutation and inspect its tenant Kafka Event, both audit-topic messages and stored audit rows, and the public query response.

##### Expected Results

- The sentinel bytes occur in none of the tenant Event, audit-topic messages, stored audit rows, or public query response. EventPublisher retains its existing Event redaction; Fulfillment builds both audit messages from allowlisted call metadata. The response record retains action, target type/ID, and outcome; under healthy delivery the call has exactly two rows with one `operation_id`.

#### TC-FR8-02: Supported credential access records target and outcome only

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | high | automated |

##### Preconditions

- A credential-access method is available through Fulfillment and has a reviewed action/target mapping.

##### Steps

1. Access a test credential through that method and query its linked audit records as a provider or inspect the database.

##### Expected Results

- The response record identifies the credential object type/ID, access action, actor, final gRPC status code name as `outcome`, and `metadata.status_code` when denied. Its linked request record has `outcome=PENDING`; neither record contains a credential value, request body, or response body.

### NFR-1: API-level append-only behavior

#### TC-NFR1-01: Public and internal APIs expose no record mutation

| Interface Change | Priority | Automation |
|---|---|---|
| IC-6 | critical | automated |

##### Preconditions

- Generated public gRPC descriptors and the HTTP gateway route table are available.

##### Steps

1. Inspect public `AuditRecords` methods and routes; attempt update/delete method names against the public gRPC server and HTTP gateway.

##### Expected Results

- Only List is public; no audit record create/update/delete method or HTTP route is registered, and attempted methods return `Unimplemented` or HTTP 404/405.
- A stored record remains unchanged after the attempts.

### NFR-2: Fail-open capture and delivery

#### TC-NFR2-01: API publication and consumer failures do not change API results

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | critical | automated |

##### Preconditions

- A resource mutation works while Fulfillment's audit-topic publication can be denied independently of EventPublisher's tenant Event path. The consumer's audit-table insertion can also be failed independently. A fixture can delay or deny Kafka acknowledgments and force-kill Fulfillment after resource commit but before the response record is acknowledged.

##### Steps

1. Delay Kafka acknowledgments and make a successful mutation. Verify the request record is acknowledged before authorization/business work and the response record before the API response returns.
2. Deny Fulfillment publication to the audit topic and make another successful mutation; verify the ordinary API result after the bounded retry/timeout and inspect the failed-publish signal. Confirm tenant Event delivery remains independent.
3. Restore publication, fail the consumer's audit-table insertion, and make another successful mutation. Verify both audit messages reach Kafka, then restore insertion and poll for their rows.
4. Redeliver the step 3 call's request and response messages with their original event IDs and query again.
5. Commit another mutation, then force-kill Fulfillment before its response record is acknowledged. Restart and inspect the object and audit rows by object ID and time window.

##### Expected Results

- With healthy Kafka, the tested mutation returns its ordinary successful result only after Kafka acknowledges its request and response records. Delayed acknowledgments delay the API response; tenant Events remain independent of audit publication or ingestion.
- When publication is denied, the mutation still returns its ordinary result after the bounded retry/timeout. Failed records are absent after recovery and their drops are observable; there is no application queue or queue-overflow path. EventPublisher produces no audit record for these calls.
- When consumer insertion fails, acknowledged messages remain on Kafka and produce one `outcome=PENDING` request row and one `outcome=OK` response row after recovery. Redelivery produces no duplicate.
- The force-killed mutation is committed but may have only its request audit record if the response record was not acknowledged. A request record proves receipt only, not success or failure.

#### TC-NFR2-02: Keycloak authentication is unaffected by listener delivery failure

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5/6 | critical | automated |

##### Preconditions

- Real Keycloak listener is active; its Kafka connection and the separate Fulfillment audit consumer's database insertion can be failed independently.

##### Steps

1. Deny the listener's Kafka connection and perform a valid login plus a wrong-password attempt.
2. Restore Kafka, fail the consumer's audit-table insertion, and perform another login. Restore insertion and query the audit trail.
3. Stop the Fulfillment API while the consumer remains running, perform another login, then restart the API and query the audit trail.

##### Expected Results

- Login succeeds and the wrong-password attempt remains an authentication failure; neither turns into a server error because of audit delivery. The listener waits only for the bounded acknowledgment/retry attempt, so failures may delay but do not change authentication results.
- Listener failure logging/counter records both dropped audit messages without password or token bytes.
- The login in step 2 succeeds; its accepted Kafka message is stored once after audit-table insertion recovers.
- The consumer stores the event from step 3 while the API is down; after restart, the query returns it once.

#### TC-NFR2-03: Delivery diagnostics are observable without record attribution values

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3/5/6 | high | automated |

##### Preconditions

- Recording log/metric sinks are available for both publishers, the consumer, and the query path. Fixtures use distinct test-only markers for tenant, actor, resource, credentials, and free-text errors. The harness can induce acknowledgment timeout, exhausted retries, invalid input, insert failure, consumer lag, and query unavailability.

##### Steps

1. Exercise healthy publication and each failure fixture. Inspect publication latency, acknowledgment timeout, failure/drop, invalid-record, insert-failure, consumer-lag, and query-availability signals.
2. Inspect captured log fields/messages and metric names/labels for all fixture markers. Inspect audit envelopes and rows for raw payloads and free-text errors.

##### Expected Results

- The relevant signals distinguish publication failures/drops from consumer insertion failures and invalid records. Both publishers expose their fail-open drops; no numeric alert threshold or product latency SLO is assumed.
- Logs and metrics contain no tenant, actor, resource, or credential values. Audit messages and rows contain only the allowed record fields and source-specific codes, never raw request/response/event payloads, credential contents, or free-text errors.

#### TC-NFR2-04: Consumer commits offsets only after durable database commit

| Interface Change | Priority | Automation |
|---|---|---|
| IC-6 | critical | automated |

##### Preconditions

- A disposable real Kafka broker, PostgreSQL database, and audit consumer are available. A fault harness can pause and terminate the consumer before database commit and after database commit but before Kafka offset commit, inspect the group's committed offsets, and restart with the same group. Retention exceeds the test duration; valid fixtures have known event IDs and partition offsets.

##### Steps

1. Publish a valid fixture and pause its insertion before database commit. Verify the group's committed offset has not advanced past that message, then terminate the consumer and confirm its uncommitted row is absent.
2. Restart the consumer with the same group and poll every 2 seconds for up to 60 seconds for the fixture row and subsequent offset advancement.
3. With another fixture, pause after database commit but before offset commit. Verify the row is durable and the group's committed offset has not advanced past that message, then terminate the consumer.
4. Restart with the same group. Observe redelivery and deduplication, then poll every 2 seconds for up to 60 seconds for offset advancement. Publish a later valid message on the same partition and verify it is ingested within the same polling bound.

##### Expected Results

- No offset advances past a valid message whose database transaction has not committed. A crash before database commit leaves that message eligible for replay, and recovery stores exactly one row.
- A crash between database commit and offset commit leaves one durable row and causes redelivery after restart. Deduplication by event ID leaves that row unchanged, permits offset advancement, and does not block the following valid message.
- The test observes real database commits and Kafka group offsets; mocked commit ordering alone does not satisfy this boundary. The polling bounds are test limits, not a product recovery SLO.

### NFR-3: Audit storage remains within the deployment jurisdiction

#### TC-NFR3-01: Deployment identities and audit write permissions

| Interface Change | Priority | Automation |
|---|---|---|
| IC-7 | high | automated |

##### Preconditions

- The platform chart renders with bundled PostgreSQL and Kafka, and with external endpoints in a separate fixture. Disposable Kafka and PostgreSQL instances are available for permission checks.

##### Steps

1. Render both configurations and inspect TLS, SCRAM-SHA-512, the pre-created audit topic, the dedicated Fulfillment audit-publisher credential, EventPublisher's existing credential, the separate Keycloak and consumer credentials, the Keycloak credential's availability before listener startup, exact-topic/group ACLs, audit-table migration owner, database roles, and backup selection.
2. Against disposable Kafka, publish with the Fulfillment audit-publisher and Keycloak identities; try reading with them, writing with the consumer identity, and reading or writing with an unrelated identity. Confirm EventPublisher's existing identity cannot write to the audit topic.
3. Against disposable PostgreSQL, insert with `audit_consumer` and select with `audit_reader`; try inserting, updating, and deleting audit rows with `audit_reader`, updating or deleting with `audit_consumer`, mutating resource tables with `audit_consumer`, and running a migration with either runtime role.

##### Expected Results

- The bundled fixture stores audit rows in Fulfillment's PostgreSQL database, includes the table in backup/replication, connects the Fulfillment API and Keycloak listener as publishers to one audit topic using separate credentials, and deploys one separate Fulfillment consumer with no separate audit service. EventPublisher retains its existing identity and continues to publish only tenant resource Events.
- The dedicated Fulfillment audit-publisher and separate Keycloak identities can write the pre-created audit topic but cannot read it. EventPublisher's identity cannot write to the audit topic. Only the consumer can read with its named group; it cannot write. An unrelated identity cannot read or write.
- Bundled Kafka uses TLS and SCRAM-SHA-512. Publishers have Write, Describe, and IdempotentWrite permissions; the consumer has Read and Describe permissions restricted to the audit topic and its named group. Verify authenticated encrypted connections against the disposable broker, not rendered configuration alone.
- Only `audit_consumer` can append an audit row; `audit_reader` can select it. Neither role can update/delete audit rows or run a migration, and the consumer cannot mutate resource tables.
- The external fixture requires equivalent authenticated Kafka identities and ACLs, and exposes Kafka/database endpoints and the jurisdiction prerequisite for operator review; no assertion of physical co-location is made from URLs alone.

### NFR-4: Indefinite retention in the first increment

#### TC-NFR4-01: Records survive restart and no retention job deletes them

| Interface Change | Priority | Automation |
|---|---|---|
| IC-6 | high | automated |

##### Preconditions

- An audit record is stored; Fulfillment and PostgreSQL restart can be performed in a disposable environment.

##### Steps

1. Restart the API, audit consumer, and database, query the record, and inspect migrations, scheduled jobs, and chart values for any audit-table TTL or cleanup.

##### Expected Results

- The same record ID and fields are returned after restart; no audit-table TTL, cleanup job, or stored-record retention setting exists in the 0.5 deployment. Kafka's finite transport retention does not delete stored rows.

#### TC-NFR4-02: Disable and re-enable audit without losing stored or retained records

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3/6/7 | high | automated |

##### Preconditions

- A disposable deployment has real Fulfillment, Kafka, PostgreSQL, and the separate audit consumer. A known audit row exists. The implementation's rollback/disable and re-enable procedure is documented; its controls and unavailable-query response are not specified by the design and must not be invented by this test. Kafka retention exceeds the disabled interval.

##### Steps

1. Snapshot the existing row's ID and fields. Apply the documented procedure to disable Fulfillment capture and audit queries while pausing the consumer, retaining its group offsets and audit storage.
2. Perform an otherwise audited resource mutation and attempt an audit query. Verify the mutation's ordinary result and that disabled capture makes no audit publication for these calls; inspect retained rows directly in PostgreSQL.
3. While ingestion is paused, publish known valid audit fixtures to Kafka and confirm broker acceptance. Record their IDs and offsets and verify they remain retained before re-enabling.
4. Re-enable capture, queries, and the consumer using its existing group. Poll every 2 seconds for up to 60 seconds for the retained fixtures through the query API, then perform a fresh audited mutation and check its request/response pair using the same polling bound.

##### Expected Results

- Disabling capture and queries does not delete or change stored rows or prevent the resource mutation. Audit queries are unavailable according to the documented procedure, without assuming an unspecified status code.
- After re-enabling, the original row has identical fields, each Kafka-retained fixture is queryable exactly once, and fresh calls are captured normally. No earlier activity or disabled-interval call without a Kafka message is backfilled.
- Replay is asserted only for messages demonstrably retained by Kafka; the test does not promise recovery beyond topic retention. Polling bounds are test limits, not a product ingestion SLO.

## Decomposition Addendum — Installation Pipeline and Listener Shutdown

The decomposition identified these additional required boundaries. Existing
case bodies above are unchanged. All additions are planned, not executed.

### TC-NFR2-05: Listener shutdown bounds in-flight publication

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | high | automated |

**Preconditions:** the listener module, documented shutdown policy and concrete
retry/ack/shutdown settings exist. A harness can hold an acknowledgment in flight.

**Steps:** start a selected event's publication; request shutdown before its
acknowledgment; test both acknowledgment completion and exhausted bounded waiting.
Inspect recorded calls, elapsed time and safe diagnostic sinks.

**Expected:** shutdown follows the documented policy within its configured bound;
in-flight failures/drops are observable without credentials or attribution values.
Authentication results are unchanged. No numeric timeout or drain guarantee is
invented here. Identity DEV owns Unit/Contract coverage in Story 3.02; the
listener harness/runner remains unresolved until that module exists.

### TC-NFR3-02: Enclave plugin adopts installer audit schema

| Interface Change | Priority | Automation |
|---|---|---|
| IC-7 | high | automated |

**Preconditions:** audit values/schema and the consuming plugin version are pinned.

**Steps:** load the actual installer schema through the plugin; submit representative
valid/default/invalid audit configuration, including exposed disable/re-enable
controls; inspect serialized installer input and unrelated settings.

**Expected:** names, types, defaults, descriptions and validation are preserved;
valid values round-trip unchanged and invalid values are rejected. Enclave DEV
owns Unit/Contract coverage in Story 1.10. Plugin repository/runner is unresolved;
rendered Helm alone does not prove plugin consumption.

### TC-NFR3-03: Wizard renders and round-trips audit controls

| Interface Change | Priority | Automation |
|---|---|---|
| IC-7 | high | automated |

**Preconditions:** the real Wizard consumes the plugin/schema version verified above.

**Steps:** render controls, verify schema-derived control type/default/description,
enter valid and invalid values, submit, and inspect generated installer configuration.

**Expected:** controls and validation match schema, valid settings reach installer
input unchanged and invalid submission is blocked; unrelated settings are preserved.
Schema-standard controls need no custom audit UI. Enclave implementation owner
owns automated Contract/integration verification in Story 1.11; repository/UI
runner unresolved. No live Kafka/DB/provider is implied by this boundary.

## Planning Evidence and Execution Boundaries

The matrix distinguishes proposed cases from an identified runner. `DEV` owns Unit, Contract, and component-integration work; `QE` owns deployed cross-component E2E work. A path marked **proposed** does not yet provide execution evidence. Real/fake boundaries below are planned and must be established by the implementing task before a case is called covered. [Integration testing policy](https://github.com/osac-project/osac/blob/main/docs/INTEGRATION-TESTING.md#planning-evidence).

| Behavior / references / cases | Owner and tier | Suite or proposed location; command and working directory | Real boundary; simulated or omitted dependencies | Gap |
|---|---|---|---|---|
| Consumer database/offset crash ordering (NFR-2; IC-6; TC-NFR2-04; design §2.8.2) | Fulfillment DEV, component integration | Proposed `fulfillment-service/it/it_audit_recovery_test.go`; command unresolved until a controlled consumer crash/restart harness exists, working directory `fulfillment-service/`. | Real Kafka group offsets, PostgreSQL transactions, and audit consumer process; valid fixture messages and deterministic crash barriers; no Keycloak or provider. | New fault harness and runner unresolved; no ticket yet. Prove no offset commit before database commit, replay after either crash boundary, deduplication, and progress for the next message. |
| Disable/re-enable compatibility and retained replay (NFR-4, NFR-2; IC-3/6/7; TC-NFR4-02; design §6) | Fulfillment DEV and Installer DEV, component integration | Proposed `fulfillment-service/it/it_audit_compatibility_test.go`; command unresolved until the disable/re-enable procedure and deployment fixture exist, working directory `fulfillment-service/`. | Real Fulfillment API, separate audit consumer, Kafka retention/group state, and PostgreSQL; fixture audit messages, no Keycloak or provider reconciliation. | Disable/re-enable controls, fixture, and runner unresolved; no ticket yet. Verify preserved rows, unavailable queries, disabled capture, retained replay, resumed capture, and no backfill. |
| Protobuf query/record validation, pagination, no public mutation routes (FR-5, NFR-1; IC-1/2; TC-FR5-04, TC-NFR1-01) | Fulfillment DEV, Contract | Proposed `proto/tests/` descriptor checks and Fulfillment server tests; `make lint` and `make generate` from `proto/` validate the shared source and generated contracts, while a new method test command remains unresolved. | Real public/private descriptors and in-process gRPC gateway; no audit mutation API is exposed. | New contract test location/runner to define in DEV task; no ticket yet. |
| Generic call capture and feedback mapping (FR-1/2/3/8; IC-2/3/4; TC-FR1-01/02, TC-FR2-01/02, TC-FR3-01/02, TC-FR8-01) | Fulfillment DEV, Unit | Proposed `fulfillment-service/internal/servers/audit_*_test.go`; existing Fulfillment unit command: `ginkgo run --timeout 10m internal/servers` from `fulfillment-service/`. | Real shared target extraction and feedback classification code; API result and feedback update fixtures, mocked audit publisher; no deployed controller or Keycloak. | Verify receipt time is saved before authentication and operation ID assigned on selection; classified calls publish and await acknowledgment for the request record after authentication and before authorization. Early rejection publishes the request before the response, with an actor only if authenticated. Verify distinct event IDs, shared operation ID, final result and target extraction, including generated IDs and unresolved targets. Accepted feedback adds a lifecycle row sharing the feedback call's new operation ID; rejected feedback adds none. |
| Capture classification and streaming boundaries (FR-1; IC-3; TC-FR1-03/04) | Fulfillment DEV, Contract; Stories 1.06/1.07 | Proposed `fulfillment-service/internal/servers/audit_boundary_test.go`; execution command unresolved until the in-process server/gateway harness exists, working directory `fulfillment-service/`. | Real in-process gRPC server, HTTP+JSON gateway, audit/authentication/authorization/validation/transaction/recovery interceptor chain and streaming handler; recording publisher and controlled business/auth fixtures. The transaction manager/commit result is a controlled double here; no real Kafka, database or provider. | New harness and runner owned by Stories 1.06/1.07; no separate Jira ticket. Prove method defaults, sensitivity selection, deferred denial capture, receipt time, transport deduplication, recovered status, exclusions and one pair per stream. Mocked transaction results prove interceptor observation only, not durable commit. Sensitive-read mechanism/timing remains subject to design §7.1. |
| Fulfillment call capture and Kafka delivery (FR-1/2/3/8, NFR-2; IC-2/3/4/6; TC-FR1-01/02/03, TC-FR2-01, TC-FR3-01/02, TC-FR8-01, TC-NFR2-01) | Fulfillment DEV, Unit and component integration; Stories 1.05/1.06/2.01 | Proposed `internal/servers/audit_*_test.go` plus `it/it_audit_api_test.go`; unit command above. Existing deployed baseline: `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` from `fulfillment-service/`. The controlled process-kill/ack fault harness and focused runner remain unresolved. | Unit uses transaction/publication doubles. Component integration uses real API, PostgreSQL commit outcome, Kafka acknowledgments, separate consumer, audit table and operational Event path. Broker controls delay/deny audit acks independently of EventPublisher; process barriers permit killing the API after real resource commit but before response-record acknowledgment. No real provider completion is implied. | Story 1.06 owns the new deployed commit/ack/process-kill harness and executable runner; no separate Jira ticket. Unit mocks do not satisfy the crash boundary. Verify request acknowledgment before authorization/business work, response after final transaction result, fail-open bounded delivery, safe drops and committed resource with possibly request-only history after kill/restart. Story 2.01 owns accepted-feedback lifecycle additions. |
| Public access and denial capture (FR-1/6/7/8, NFR-2; IC-3; TC-FR6-03, TC-FR7-01/02, TC-FR8-02) | Fulfillment DEV, Unit and component integration | Same proposed `internal/servers/audit_*_test.go` and `it/it_audit_api_test.go` runner. | Real public API, audit topic, consumer, and audit table, including resource mutations and audit queries. | Current deployed suite does not include audit access/denial assertions; extend it in DEV work. |
| Audit-table persistence and scoped query (FR-1/5, NFR-4; IC-1/6; TC-FR1-01, TC-FR5-01/02/03, TC-NFR4-01) | Fulfillment DEV, component integration | Proposed `fulfillment-service/it/it_audit_storage_test.go`; existing deployed Fulfillment runner above. | Real audit consumer, Fulfillment query API, and PostgreSQL audit table; Keycloak listener fixture-driven. | Add audit-table migration, indexes for recent, tenant, operation, actor, and resource lookups, and restart coverage in owning DEV work. Check action and outcome query plans at representative volume before adding further indexes. |
| Both-source protobuf consumption and tenant-scope contract (FR-4/5/6/7, NFR-2; IC-1/2/5/6; TC-FR4-01/03, TC-FR5-01/02, TC-FR6-01/02, TC-FR7-02, TC-NFR2-01/02) | Fulfillment DEV, Contract | Proposed `fulfillment-service/it/it_audit_scope_test.go`; existing deployed Fulfillment runner above. | Real binary protobuf messages from both producers, separately deployed audit-topic consumer, database writes, and public scoped query; Keycloak listener simulated. | Validate protobuf decoding, schema version, required enum values, `operation_id`, and tenant attribution; deduplicate all record IDs including lifecycle and Keycloak records, skip invalid messages without blocking later records, and prove ingestion does not call the API. |
| Keycloak listener event and organization mapping (FR-4/8, NFR-2; IC-5; TC-FR4-01/02/03, TC-NFR2-02) | Identity integration DEV, Contract | Proposed listener integration suite using Keycloak 26.6.4 and Kafka; command unresolved until listener module exists. | Real Keycloak event SPI, organization membership, audit-topic publication, separate Fulfillment consumer, and audit query. | No existing listener suite or follow-up ticket. Implement source action/outcome mappings, map a target account to actor when present in the Keycloak event, and verify organization mapping; failed login tenant remains null per design §2.2.3. |
| Safe delivery diagnostics (FR-8, NFR-2; IC-3/5/6; TC-NFR2-03) | Fulfillment DEV and Identity integration DEV, Unit | Proposed publisher/consumer/query tests with recording log/metric sinks. Fulfillment command: `ginkgo run --timeout 10m internal/servers` from `fulfillment-service/`; listener command unresolved until its module exists. | Real signal emission and allowlisting code with test markers; publisher, database, and availability failures injected; no deployed stack. | New diagnostic fixtures and listener runner unresolved; no ticket yet. Verify required signals and absence of attribution/credential values in logs and metric labels, as well as payload/error minimization in emitted records. |
| Chart and realm wiring (FR-1/4, NFR-3; IC-3/5/7; TC-FR4-01, TC-NFR3-01) | Installer DEV, Contract | Proposed Helm render assertions and disposable Kafka/PostgreSQL permission checks; `make helm-validate` from `osac-installer/` is an existing baseline, not a full audit wiring test. | Real rendered Helm/realm artifacts plus TLS/SCRAM-authenticated Kafka ACL attempts and database-role checks; Keycloak and Fulfillment workloads are not running in this case. | Audit-specific render, encrypted authentication, ACL and database-role checks, configured topic retention window, and external-jurisdiction review need implementation evidence; no ticket yet. |
| Deployed tenant/provider journey (FR-1–FR-8; IC-1–IC-7; TC-FR2-01, TC-FR4-01/02, TC-FR6-01/02/03, TC-FR7-01, TC-FR8-01) | QE, E2E | Proposed `tests/e2e/audit/test_audit_api.py`; command unresolved until deployed fixture and suite selection exist. | Real Keycloak, Fulfillment API, separate Fulfillment audit consumer, Kafka audit topic, PostgreSQL, and public gRPC/HTTP; provider reconciliation is required only for an outcome case. | No existing audit E2E fixture or ticket; new QE work must own it. |
| Outcome timing across API, audit table, and reconciler (FR-3; IC-3/4; TC-FR3-01/02) | QE, E2E | Same proposed audit suite; command unresolved. Trigger: accepted Create. Observe its linked `PENDING` request record and `OK` response record, then the feedback call's linked `PENDING` request, `OK` response, and separate lifecycle record whose outcome matches `object.status.state` and whose timestamp matches `object.status.state_transition_time`, polling every 2 seconds with a 10-minute pass/fail bound; do not fake status or rely on periodic audit backfill. | Real deployed controller/provider path selected by the feedback action registry; no mock completion. | Resource and deployed provider fixture for this journey are unresolved; no ticket yet. |

### Decomposition Addendum Planning Evidence

| Behavior / cases | Owner and tier | Suite / command / working directory | Real boundary; simulated or omitted | Gap |
|---|---|---|---|---|
| In-flight listener shutdown; TC-NFR2-05, IC-5 | Identity DEV, Unit/Contract; Story 3.02 | Proposed listener harness; command and working directory unresolved until module exists. | Actual shutdown/publish lifecycle; controlled acknowledgment/clock; real SPI lifecycle for Contract; no provider. | Concrete policy/bounds and runner unresolved; Story 3.02 owns, no separate Jira ticket. |
| Plugin adoption; TC-NFR3-02, IC-7 | Enclave DEV, Unit/Contract; Story 1.10 | Plugin repo, suite and command unresolved. | Actual plugin schema load/serialization against pinned installer schema; no live Kafka/DB/provider. | Story 1.10 owns discovery/runner; no separate Jira ticket. |
| Wizard controls; TC-NFR3-03, IC-7 | Enclave implementation owner, Contract/integration verification; Story 1.11 | Wizard repo, automated UI harness and command unresolved. | Real controls from plugin/schema and generated installer input; no live Kafka/DB/provider. | Story 1.11 owns discovery/runner; no separate Jira ticket. |

## Gaps

### Traceability Coverage Gaps

- **FR-1 partial:** The complete Fulfillment method inventory and source-specific action/target mappings must be supplied during implementation under design §2.4.1, including the audit-query action used by TC-FR7-01/02. Action literals and selected Keycloak event examples above remain proposed until those mappings are reviewed. Sensitive-read identification and any per-call classification timing remain open in §7.1. TC-FR1-03/04 plan the method, transport, denial, and stream boundaries; their new harness is not execution-ready. Do not extend capture beyond the design's Fulfillment/Keycloak sources based on older scope notes.
- **FR-3 partial:** Feedback action mappings must be inventoried during implementation under design §2.4.1. Design §2.2.3 maps `status.state` to lifecycle `outcome` and `status.state_transition_time` from the Update payload to `event_timestamp`; the five resource exceptions and missing/invalid timestamp behavior remain open in §7.2. TC-FR3-02 includes accepted ordinary/repeated updates and rejected feedback, but cannot claim a running boundary yet. Each feedback call uses a new operation ID; no test may infer a link to Create from object ID alone. Original-operation propagation is not part of this design.
- **FR-4 partial:** Design §2.2.3 resolves failed-login visibility and attribution: all such records are provider-only with null tenant; actor is the targeted account when the Keycloak event includes it. The listener's selected event/action/outcome and organization mappings remain implementation work. TC-FR4-01/03 are planned assertions, not current evidence.
- **FR-8 partial:** TC-FR8-02 requires a concrete credential-access method with a reviewed action/target mapping. The plan has not pinned that method in the registry; do not claim this path execution-ready until it does.
- **NFR-2 partial:** Replay is bounded by configured Kafka topic retention (§2.8.2/§2.9.2); it is not guaranteed beyond that window. Retry counts, acknowledgment timeout defaults, and Keycloak in-flight shutdown handling are implementation-defined in §2.8.1. Fault fixtures must record those settings before timeout/recovery assertions are executable. TC-NFR2-03 additionally requires diagnostic sinks and safe-output fixtures. TC-NFR2-04 requires real database/offset crash barriers and a new runner; Fulfillment DEV owns this unresolved harness, with no ticket yet.
- **NFR-3 partial:** A chart render proves configured endpoints, not jurisdiction of externally managed Kafka, PostgreSQL, or backups. Installer DEV must establish an operator-verifiable deployment prerequisite; the external fixture does not prove physical location. No owning follow-up ticket exists yet.

### Compatibility Execution Gap

- TC-NFR4-02 plans design §6's disable/re-enable and retained-message replay assertions. Fulfillment DEV and Installer DEV must define the operational procedure, controls, unavailable-query behavior, and test runner before it is executable. These implementation details are unresolved, with no follow-up ticket yet; the plan does not invent rollback flags or API errors.

### Interface Change Coverage Gaps

All seven interface changes have planned test cases. Their new runtime boundaries and missing runners are recorded in the planning-evidence matrix; no IC is claimed as executed.

## Summary

| Metric | Count |
|---|---:|
| Total planned test cases | 33 |
| Critical | 17 |
| High | 15 |
| Medium | 1 |
| Low | 0 |
| Automated | 33 |
| Manual | 0 |
| Traceability labels with planned cases | 12 / 12 |
| Interface changes with planned cases | 7 / 7 |
