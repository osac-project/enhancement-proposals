# Test Plan — OSAC-6161 Tenant External Billing Identity

## Overview

- **Design:** [Design](design.md)
- **PRD:** [Requirements](prd.md)
- **Total test cases:** 21

Execution entries identify source assertions on OSAC main. Gap entries describe unresolved tests for
the named work owner. No individual assignee or follow-up ticket is recorded here.

TC-E2E-03 retains its original case ID and identifies the consumer helper at its actual tier, Unit.

## Private write and public projection

#### TC-API-01: Private Create, Get and List return the stored billing ID

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Private TenantSpec.external_billing_id](design.md#api-extensions) and
  [Design — Billing identity tests](design.md#test-plan)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted.
- **Execution:** `fulfillment-service/internal/servers/private_tenants_server_test.go`
- **Evidence:** `TestServers / Stores the id on create and returns it from Get and List` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/servers/private_tenants_server_test.go)).
- **Selector:** `go test ./internal/servers -run '^(TestServers)$' -ginkgo.focus='Stores the id on create and returns it from Get and List'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Use a fresh fulfillment server fixture and the tenant name `billing-tenant`.

1. Call private Tenants/Create with `spec.external_billing_id=acct-1`.
2. Read the JSONB field, call private Get by ID, and List filtered by tenant name.

**Expected results.** Create, the tenant JSONB row, Get and the single filtered List result all contain `acct-1`.

#### TC-API-02: Public tenant responses omit the stored billing ID

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Private TenantSpec.external_billing_id](design.md#api-extensions)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted.
- **Execution:** `fulfillment-service/internal/servers/tenants_server_test.go`
- **Evidence:** `TestServers / Omits the external billing id` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/servers/tenants_server_test.go)).
- **Selector:** `go test ./internal/servers -run '^(TestServers)$' -ginkgo.focus='Public tenants server.*(Omits the external billing id)'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Create `billing-tenant` through the private API with billing ID `acct-1`.

1. Call public Tenants/Get by its ID and public List filtered by name.
2. Encode the returned tenant objects as proto JSON.

**Expected results.** Get JSON omits both `external_billing_id` and `externalBillingId`. List has one item
and its JSON omits `externalBillingId`.

#### TC-API-03: Private writes enforce the 256-character boundary

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Private TenantSpec.external_billing_id](design.md#api-extensions) and
  [Design — Billing identity propagation](design.md#workflow-description)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted. The Create
  interceptor and Update path validation run in process.
- **Execution:** `fulfillment-service/internal/servers/private_tenants_server_test.go`
- **Evidence:** `TestServers / Accepts an id of 256 characters and rejects a longer one` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/servers/private_tenants_server_test.go)).
- **Selector:** `go test ./internal/servers -run '^(TestServers)$' -ginkgo.focus='Accepts an id of 256 characters and rejects a longer one'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Use separate Create requests with 256 and 257 repeated ASCII characters. Create
an additional tenant with `acct-1` for the Update case.

1. Call private Create through protovalidate with each value.
2. Mask-update `spec.external_billing_id` to a 257-character value and re-read the stored tenant.

**Expected results.** Create with 256 characters succeeds. Create and Update with 257 return
InvalidArgument. The rejected Create is absent and the existing tenant retains `acct-1`.

#### TC-API-04: Maskless Update that omits the ID clears it

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Private TenantSpec.external_billing_id](design.md#api-extensions) and
  [Design — Billing identity propagation](design.md#workflow-description)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted.
- **Execution:** `fulfillment-service/internal/servers/private_tenants_server_test.go`
- **Evidence:** `TestServers / Clears the id when an update omits it` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/servers/private_tenants_server_test.go)).
- **Selector:** `go test ./internal/servers -run '^(TestServers)$' -ginkgo.focus='Clears the id when an update omits it'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Seed `billing-tenant` with `acct-1` and clone the current full private Tenant object.

1. Clear the field in the cloned spec and send private Tenants/Update without a mask.
2. Read the tenant with private Get.

**Expected results.** Update succeeds and Get reports the optional field absent.

#### TC-API-05: Maskless Update that resends the ID preserves it

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Private TenantSpec.external_billing_id](design.md#api-extensions) and
  [Design — Billing identity propagation](design.md#workflow-description)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted.
- **Execution:** `fulfillment-service/internal/servers/private_tenants_server_test.go`
- **Evidence:** `TestServers / Keeps the id when an update sends the same value` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/servers/private_tenants_server_test.go)).
- **Selector:** `go test ./internal/servers -run '^(TestServers)$' -ginkgo.focus='Keeps the id when an update sends the same value'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Seed `billing-tenant` with `acct-1` and clone the current full private Tenant object.

1. Send the cloned object to private Tenants/Update without a mask.
2. Read the tenant with private Get.

**Expected results.** Update succeeds and Get still returns `acct-1`.

#### TC-API-06: Private Update persists a replacement billing ID

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Private TenantSpec.external_billing_id](design.md#api-extensions) and
  [Design — Billing identity tests](design.md#test-plan)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment servers/DAOs. Suite
  doubles supply tenancy and attribution. The deployed gateway and provider are omitted.
- **Execution:** `fulfillment-service/internal/servers/private_tenants_server_test.go`
- **Evidence:** `TestServers / Replaces the id when an update sends a new value` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/servers/private_tenants_server_test.go)).
- **Selector:** `go test ./internal/servers -run '^(TestServers)$' -ginkgo.focus='Replaces the id when an update sends a new value'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Seed `billing-tenant` with `acct-1`.

1. Change the cloned spec to `acct-2` and send private Tenants/Update without a mask.
2. Read the tenant with private Get.

**Expected results.** Update succeeds and Get returns `acct-2`. TC-PIPE-02 checks Fold behavior on stamped
events, and TC-E2E-02 checks the deployed outcome of the change.

#### TC-API-07: The generated public TenantSpec descriptor excludes the billing ID

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Private TenantSpec.external_billing_id](design.md#api-extensions)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
- **Gap:** The public server test proves JSON omission for a populated tenant. A direct generated
  TenantSpec descriptor regression assertion is unresolved.

**Preconditions.** Load the generated private and public TenantSpec descriptors.

1. Look up `external_billing_id` and its JSON name in the private descriptor.
2. Look up both names in the public descriptor.

**Expected results.** The private descriptor has the optional field and its corresponding JSON name. The
public descriptor exposes neither name.

## Envelope, history and outbox

#### TC-PIPE-01: The publisher stamps the current tenant value on each event in a batch

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Private Event.external_billing_id](design.md#api-extensions) and [Design
  — Billing identity propagation](design.md#workflow-description)
- **Dependencies:** Real PostgreSQL change rows, publisher and Kafka broker fixture. The change rows
  are synthetic and no downstream Fold or provider runs.
- **Execution:** `fulfillment-service/internal/servers/event_publisher_test.go`
- **Evidence:** `TestServers / Stamps the current billing id on every event in one batch` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/fulfillment-service/internal/servers/event_publisher_test.go)).
- **Selector:** `go test ./internal/servers -run '^(TestServers)$' -ginkgo.focus='Stamps the current billing id on every event in one batch'` from `fulfillment-service` in osac. Not run for this backfill.

**Preconditions.** Use one synthetic tenant with `acct-1`, another with a tenant row but omitted ID,
and a third without a row. Insert tracked project changes for all three.

1. Start the publisher and read the Kafka batch for each tenant.
2. Inspect optional billing ID presence on every envelope.

**Expected results.** All four tracked envelopes for the billing tenant carry `acct-1`. The three envelopes
for the tenant without an ID and the one for the missing-row fixture omit the field.

#### TC-PIPE-02: The Fold writes a billing fact when the envelope value changes

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Private Event.external_billing_id](design.md#api-extensions) and [Design
  — Billing identity propagation](design.md#workflow-description)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider.
- **Execution:** `osac-metering/metering-service/internal/fold/fold_test.go`
- **Evidence:** `TestFoldRecordsExternalBillingIDWhenItChanges` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/fold/fold_test.go)).
- **Selector:** `go test ./internal/fold -run '^(TestFoldRecordsExternalBillingIDWhenItChanges)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use tenant `billing-fold` with no prior fact and seven dated envelopes carrying
empty, empty, acct-1, acct-1, acct-2, empty, empty in that offset order.

1. Publish and fold all seven.
2. Read tenant billing facts, reset the input offset, and fold the same log again.

**Expected results.** Exactly four rows remain, one each at the first empty, first acct-1, acct-2 and first
subsequent empty envelope. Replaying the log adds no rows.

#### TC-PIPE-03: The Fold excludes an envelope for a foreign tenant

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Private Event.external_billing_id](design.md#api-extensions) and [Design
  — Tenant scope](design.md#rbac--tenancy)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider.
- **Execution:** `osac-metering/metering-service/internal/fold/fold_test.go`
- **Evidence:** `TestFoldIgnoresBillingIDOnForeignTenantEvent` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/fold/fold_test.go)).
- **Selector:** `go test ./internal/fold -run '^(TestFoldIgnoresBillingIDOnForeignTenantEvent)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use topic tenant `billing-foreign` with a local `acct-1` envelope. Use a
synthetic second record whose ComputeInstance metadata names tenant `beta` and envelope carries
`acct-other`.

1. Publish both to the fixture topic, preserving the foreign payload’s tenant.
2. Fold through both offsets and read resource and billing rows.

**Expected results.** Only the local `acct-1` fact exists. No fact is written for resource `vm-foreign`.

#### TC-PIPE-04: The Fold uses a dated billing envelope even without a recognized payload

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Private Event.external_billing_id](design.md#api-extensions) and [Design
  — Billing identity propagation](design.md#workflow-description)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider.
- **Execution:** `osac-metering/metering-service/internal/fold/fold_test.go`
- **Evidence:** `TestFoldSkipsUndatedBillingChange + TestFoldRecordsBillingIDWhenPayloadIsUnknown` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/fold/fold_test.go)).
- **Selector:** `go test ./internal/fold -run '^(TestFoldSkipsUndatedBillingChange|TestFoldRecordsBillingIDWhenPayloadIsUnknown)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Prepare one envelope with `acct-1` and no timestamp, a dated follow-up carrying
that value, and a separate dated `acct-1` envelope with no recognized payload.

1. Fold the undated and then dated pair and inspect stored history and the missing-time counter.
2. Fold the payload-less fixture in a separate tenant and read the billing fact.

**Expected results.** The undated input increments the skip counter by one and only the dated follow-up
creates a row. The separate dated envelope writes `acct-1` at its own timestamp.

#### TC-PIPE-05: The Round labels new heartbeats from the latest Fold fact

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — HeartbeatData.external_billing_account_id](design.md#api-extensions) and
  [Design — Billing identity propagation](design.md#workflow-description)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider. No Relay is needed because the assertion is on pending outbox rows.
- **Execution:** `osac-metering/metering-service/internal/round/round_test.go`
- **Evidence:** `TestRoundCarriesTheLatestExternalBillingAccountID + TestRoundCarriesBillingAccountFromLaterEventOffset` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/round/round_test.go)).
- **Selector:** `go test ./internal/round -run '^(TestRoundCarriesTheLatestExternalBillingAccountID|TestRoundCarriesBillingAccountFromLaterEventOffset)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use a RUNNING small VM with create envelope `acct-1` and a follow-up carrying
`acct-2`. In a separate fixture, put `acct-1` at the later offset but earlier timestamp.

1. Fold the create, run the first Round, and store the outbox bytes by ID.
2. Fold the change and run the next Round.
3. Run the offset-order fixture through its first Round.

**Expected results.** Earlier outbox rows found in the second read have unchanged bytes. At least one
new row appears and each new row carries `acct-2`. Every row in the offset-order fixture carries `acct-1`.

#### TC-PIPE-06: The Round omits the account field when the tenant has none

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — HeartbeatData.external_billing_account_id](design.md#api-extensions)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider. No Relay is needed for the outbox assertion.
- **Execution:** `osac-metering/metering-service/internal/round/round_test.go`
- **Evidence:** `TestRoundOmitsExternalBillingAccountIDWhenTheTenantHasNone` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/round/round_test.go)).
- **Selector:** `go test ./internal/round -run '^(TestRoundOmitsExternalBillingAccountIDWhenTheTenantHasNone)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use a synthetic RUNNING VM with no billing ID on its envelope.

1. Produce and fold the create event.
2. Run the first minute Round and inspect each outbox heartbeat.

**Expected results.** At least one heartbeat exists. Every decoded account field is nil and every serialized
payload omits `external_billing_account_id`.

#### TC-PIPE-07: The heartbeat builder serializes the account only when supplied

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — HeartbeatData.external_billing_account_id](design.md#api-extensions)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
- **Execution:** `osac-metering/metering-service/internal/heartbeat/event_test.go`
- **Evidence:** `TestNewSetsExternalBillingAccountIDOnlyWhenPresent` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/heartbeat/event_test.go)).
- **Selector:** `go test ./internal/heartbeat -run '^(TestNewSetsExternalBillingAccountIDOnlyWhenPresent)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use ledger key `vm-1`, meter and component `compute`, tenant `acme`, and a
one-minute interval with quantity 60 seconds.

1. Build once with `acct-1` and once with the empty string.
2. Decode each payload and check JSON field presence.

**Expected results.** The first payload carries `acct-1`. The second has nil decoded account and omits the key.

#### TC-PIPE-08: M360 translation omits the account field from its payload

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Provider adapter field
  handling](design.md#implementation-detailsnotesconstraints) and [Design —
  HeartbeatData.external_billing_account_id](design.md#api-extensions)
- **Dependencies:** In-process fixtures only; no database, broker, deployment, or billing provider.
- **Execution:** `osac-metering/adapters/m360/translate_test.go`
- **Evidence:** `TestM360Adapter / omits external_billing_account_id from the m360 payload` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/adapters/m360/translate_test.go)).
- **Selector:** `go test ./m360 -run '^(TestM360Adapter)$' -ginkgo.focus='omits external_billing_account_id from the m360 payload'` from `osac-metering/adapters` in osac. Not run for this backfill.

**Preconditions.** Use compute heartbeat `hb-billing` for VM `vm-7`, 60 seconds, with
`external_billing_account_id=acct-1` in its serialized data.

1. Translate the heartbeat to an M360 payload.
2. Inspect the translated field map.

**Expected results.** Translation succeeds and the output map lacks `external_billing_account_id`.

#### TC-PIPE-09: A deletion reversal retains the original billing account

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — HeartbeatData.external_billing_account_id](design.md#api-extensions) and
  [Design — Billing identity propagation](design.md#workflow-description)
- **Dependencies:** Real Kafka and PostgreSQL test containers and the metering service components
  under test. The harness supplies fulfillment snapshots and omits the fulfillment server and
  billing provider. No Relay is needed for the reversal assertion.
- **Execution:** `osac-metering/metering-service/internal/round/round_test.go`
- **Evidence:** `TestRoundKeepsBillingAccountOnDeletionReversal` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/osac-metering/metering-service/internal/round/round_test.go)).
- **Selector:** `go test ./internal/round -run '^(TestRoundKeepsBillingAccountOnDeletionReversal)$'` from `osac-metering/metering-service` in osac. Not run for this backfill.

**Preconditions.** Use a RUNNING small VM with `acct-1`, an initial positive Round at +1 minute, and
stamped VM and tenant deletes at +30 and +40 seconds.

1. Fold the delayed deletes and run another Round.
2. Parse the signed outbox quantities and check the account on each negative reversal.

**Expected results.** At least one negative reversal exists and all negative reversal rows carry `acct-1`.

#### TC-PIPE-10: A changed private Update reaches the Fold history

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Private TenantSpec.external_billing_id](design.md#api-extensions) and
  [Design — Private Event.external_billing_id](design.md#api-extensions) and [Design — Billing
  identity tests](design.md#test-plan)
- **Dependencies:** Requires the real fulfillment API, publisher, Kafka and Fold with their
  PostgreSQL stores. Use a synthetic tenant and omit the Round and provider.
- **Gap:** Separate API, publisher and Fold specs establish the individual steps. The deployed
  journey checks the final heartbeat. The joined assertion on a real API write and its exact Fold
  history fact is unresolved.

**Preconditions.** Use a committed tenant with `acct-1` and one existing billing fact created from
that tenant’s publisher output.

1. Update the tenant to `acct-2` through the private API and commit.
2. Let the publisher drain the batch and fold the resulting tenant envelope.
3. Inspect the published envelope and query metering history.

**Expected results.** The envelope carries `acct-2`, and history has one additional billing fact with
`acct-2` at that envelope’s Kafka offset. The earlier `acct-1` row is unchanged.

## Deployed topic and consumer interpretation

#### TC-E2E-01: A deployed heartbeat reflects an unset or configured account

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — Private TenantSpec.external_billing_id](design.md#api-extensions) and
  [Design — HeartbeatData.external_billing_account_id](design.md#api-extensions) and [Design —
  Billing identity tests](design.md#test-plan)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides the test readback for published records.
- **Execution:** `tests/e2e/vmaas/sanity/test_metering_billing.py`
- **Evidence:** `test_metering_external_billing_account_on_heartbeats` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/tests/e2e/vmaas/sanity/test_metering_billing.py)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_metering_billing.py::test_metering_external_billing_account_on_heartbeats` from `repository root` in osac. Not run for this backfill.

**Preconditions.** Use an already-onboarded test tenant with private access and a billable VM in its
dedicated project.

1. Clear the tenant field with mask `spec.external_billing_id`, start the VM and read a typed heartbeat.
2. Set `acct-e2e-1` with the same mask, verify private Get and wait up to 180 seconds for a
   heartbeat with a new ID.

**Expected results.** The first heartbeat accessor returns no account. Private Get reports `acct-e2e-1`, and
a new heartbeat carries that account.

#### TC-E2E-02: A billing ID change leaves existing published records unchanged

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — Billing identity propagation](design.md#workflow-description) and [PRD —
  Changes apply to future usage](prd.md#in-scope)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides the test readback for published records.
- **Execution:** `tests/e2e/vmaas/sanity/test_metering_billing.py`
- **Evidence:** `test_metering_external_billing_account_on_heartbeats` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/tests/e2e/vmaas/sanity/test_metering_billing.py)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_metering_billing.py::test_metering_external_billing_account_on_heartbeats` from `repository root` in osac. Not run for this backfill.

**Preconditions.** Use the same deployed fixture with a RUNNING VM and at least one published
heartbeat after setting `acct-e2e-1`.

1. Read the account values indexed by event ID.
2. Set `acct-e2e-2` with a private Update mask and wait up to 180 seconds for a new heartbeat with
   that account.
3. Re-read the same resource’s published events through Echo.

**Expected results.** A fresh ID carries `acct-e2e-2`. Each previously captured ID with `acct-e2e-1`
still returns that account through Echo.

#### TC-E2E-03: The consumer accessor treats a missing or empty account as absent

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — HeartbeatData.external_billing_account_id](design.md#api-extensions)
- **Dependencies:** In-process dictionaries only. The selector excludes the enclosing E2E
  configuration so its autouse fixtures do not start deployed tenant setup.
- **Execution:** `tests/e2e/core/test_metering.py`
- **Evidence:** `test_billing_account_id_treats_missing_and_empty_as_absent` ([source](https://github.com/osac-project/osac/blob/2a69f3d27c2341da4dd4fe8965bc7cfadcf90d69/tests/e2e/core/test_metering.py)).
- **Selector:** `uv run pytest --noconftest -n 0 tests/e2e/core/test_metering.py::test_billing_account_id_treats_missing_and_empty_as_absent` from `repository root` in osac. Not run for this backfill.

**Preconditions.** Prepare three local heartbeat dictionaries whose data omits the account, has an
empty string, or has `acct-1`.

1. Call the consumer accessor on all three dictionaries.
2. Compare the returned values.

**Expected results.** The accessor returns None, None, and `acct-1`, respectively.

#### TC-E2E-04: Clearing an already-published account omits the field on fresh heartbeats

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — Private TenantSpec.external_billing_id](design.md#api-extensions) and
  [Design — HeartbeatData.external_billing_account_id](design.md#api-extensions) and [Design —
  Billing identity tests](design.md#test-plan)
- **Dependencies:** Real deployed fulfillment, hub controllers, Kafka and metering. The Echo adapter
  provides the test readback for published records.
- **Gap:** The deployed case observes absence before setting an account and covers replacing it
  later. The set-to-clear transition and raw-key assertion on deployed records remain unresolved.

**Preconditions.** Use an existing tenant and RUNNING VM whose latest published heartbeat carries
`acct-e2e-1`.

1. Clear the field through private Update and confirm absence with Get.
2. Wait for a later heartbeat with a new ID.
3. Inspect the new heartbeat’s raw JSON and re-read the original ID.

**Expected results.** The new JSON omits the account key within 180 seconds and the earlier ID still carries
`acct-e2e-1`.
