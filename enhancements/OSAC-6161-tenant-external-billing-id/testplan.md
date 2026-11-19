# Test Plan — OSAC-6161 Tenant External Billing Identity

## Overview

- **Feature:** OSAC-6161 — Associate a tenant with its identity in the external
  billing system
- **Design:** [design.md](design.md) (§Proposal, §API Extensions, §Test Plan)
- **PRD:** [prd.md](prd.md)
- **Total test cases:** 16

The private tenant gains `external_billing_id`. The fulfillment event publisher
stamps it on every event envelope for the tenant, the metering Fold records it
as a `history` fact when it changes, and the Round writes it into every
`HeartbeatData` it produces.

Cases below are derived from the design, not from the existing tests. Where a
test already exists it is named; where it does not, the case is a gap.

## Private API

#### TC-API-01: Create, Get, and List return the stored billing id

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | critical | automated |

- **Tier:** Component integration
- **Boundary:** private Fulfillment API -> tenant JSONB persistence
- **Gap:** no fulfillment-service test covers `external_billing_id` today.

#### TC-API-02: Public tenant responses omit the field

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | critical | automated |

- **Tier:** Component integration
- **Boundary:** private proto -> generated public proto
- **Gap:** no test asserts the public message has no such field.

#### TC-API-03: A value longer than 256 characters is rejected

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | high | automated |

- **Tier:** Component integration
- **Boundary:** protovalidate interceptor on Create and Update
- **Gap:** no boundary test for the limit.

#### TC-API-04: Update without the field clears the stored value

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | high | automated |

- **Tier:** Component integration
- **Boundary:** full object replacement in `PrivateTenantsServer`
- **Gap:** no test covers the replacement semantics.

#### TC-API-05: Update that resends the same value preserves it

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | high | automated |

- **Tier:** Component integration
- **Boundary:** full object replacement in `PrivateTenantsServer`
- **Gap:** no test covers the preserve path.

## Envelope and metering pipeline

#### TC-PIPE-01: The publisher stamps the tenant's value on every event

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | high | automated |

- **Tier:** Component integration
- **Boundary:** fulfillment publisher -> private Event envelope
- **Gap:** no test covers the per-batch tenant lookup and stamping.

#### TC-PIPE-02: The Fold records a history fact only when the value changes

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | high | automated |

- **Tier:** Unit
- **Execution:** `osac-metering/metering-service/internal/fold/fold_test.go`
- **Covers:** `TestFoldRecordsExternalBillingIDWhenItChanges`

#### TC-PIPE-03: The Fold ignores an event for a foreign tenant

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | medium | automated |

- **Tier:** Unit
- **Execution:** `osac-metering/metering-service/internal/fold/fold_test.go`
- **Covers:** `TestFoldIgnoresBillingIDOnForeignTenantEvent`

#### TC-PIPE-04: The Fold handles undated and unknown-payload events

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | medium | automated |

- **Tier:** Unit
- **Execution:** `osac-metering/metering-service/internal/fold/fold_test.go`
- **Covers:** `TestFoldSkipsUndatedBillingChange`, `TestFoldRecordsBillingIDWhenPayloadIsUnknown`

#### TC-PIPE-05: The Round carries the latest value into the heartbeat

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | critical | automated |

- **Tier:** Unit
- **Execution:** `osac-metering/metering-service/internal/round/round_test.go`
- **Covers:** `TestRoundCarriesTheLatestExternalBillingAccountID`, `TestRoundCarriesBillingAccountFromLaterEventOffset`

#### TC-PIPE-06: The Round omits the field when the tenant has no value

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | high | automated |

- **Tier:** Unit
- **Execution:** `osac-metering/metering-service/internal/round/round_test.go`
- **Covers:** `TestRoundOmitsExternalBillingAccountIDWhenTheTenantHasNone`, `TestRoundKeepsBillingAccountOnDeletionReversal`

#### TC-PIPE-07: The heartbeat builder sets the field only when present

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | medium | automated |

- **Tier:** Unit
- **Execution:** `osac-metering/metering-service/internal/heartbeat/event_test.go`
- **Covers:** `TestNewSetsExternalBillingAccountIDOnlyWhenPresent`

#### TC-PIPE-08: The m360 adapter payload never contains the field

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | critical | automated |

- **Tier:** Contract
- **Boundary:** metering heartbeat -> m360 billing adapter
- **Gap:** no contract test asserts the field is absent.

## End to end

#### TC-E2E-01: A heartbeat carries the tenant's billing id, and omits it when unset

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-4 | critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/vmaas/sanity/test_metering_billing.py`
- **Covers:** `test_metering_external_billing_account_on_heartbeats`

#### TC-E2E-02: A later change affects new heartbeats only

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-4 | high | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/core/test_metering.py`
- **Covers:** `test_published_heartbeats_keep_their_billing_account_when_later_ones_change`

#### TC-E2E-03: A missing or empty value is treated as absent

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-4 | high | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/core/test_metering.py`
- **Covers:** `test_billing_account_id_treats_missing_and_empty_as_absent`

## Gaps this plan exposes

- The private API has no test for the field: storage, public omission, the
  256-character limit, and the two Update semantics.
- The publisher stamping path has no test.
- The m360 adapter has no contract test for the omission.
