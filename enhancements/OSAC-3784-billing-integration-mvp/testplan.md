# Testplan — OSAC-3784 and OSAC-3793 Combined Billing Design

## Overview

- **Feature:** Combined OSAC-3784 — Billing Integration and OSAC-3793 — Billing Catalog Pricing Integration
- **Total test cases:** 47
- **Requirements covered:** 39 of 40
- **Interface changes covered:** 17 of 17

Requirement IDs are defined in §5 of `design.md`. FR-1 through FR-18 trace OSAC-3784 PRD stories; FR-19 through FR-22 and FR-34 trace user-directed decisions; FR-23 through FR-31 trace OSAC-3793 catalog-pricing requirements; FR-32 and FR-33 trace the catalog-input inventory and normalized provider rate-card rows; NFR-1 through NFR-6 trace cross-cutting constraints. Unless a case explicitly says billing is disabled, billing-specific cases assume one provider is configured. The catalog-pricing cases below replace the original OSAC-3793 test IDs from the pre-merge testplan.

## Test Cases

### FR-1: Submit VMaaS/CaaS usage to the configured provider

#### TC-FR1-01: Deliver one usage event once after provider retry

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | critical | automated |

##### Preconditions

- A metering event has a stable CloudEvent `source` and `id`; the linked M360 billing account has `externalId` set to the event's `tenant_id`.
- The provider test endpoint returns a retryable error once, then accepts the event.

##### Steps

1. Publish the event to the metering Kafka topic.
2. Allow the adapter to retry after the first provider error.

##### Expected Results

- The provider receives the event with the effective account target and stable event ID.
- The adapter records one accepted event and commits the Kafka offset only after acceptance.

### FR-2: Associate a tenant with an existing account, current 1:1 rule, and account currency

#### TC-FR2-01: Link an active existing account and reject conflicts

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2 | high | automated |

##### Preconditions

- A platform billing admin can access an active existing provider account with a valid ISO-4217 currency.
- Another active billing account is already linked to a different tenant.

##### Steps

1. Link the available account to an unlinked tenant using the billing-profile API.
2. Attempt to link that account to a second tenant.
3. Attempt to link an inactive account.

##### Expected Results

- The first request returns the normalized account ID, currency, and `CONNECTED` state after provider verification.
- The second request returns `FAILED_PRECONDITION/ACCOUNT_ALREADY_LINKED` and leaves both assignments unchanged.
- The inactive-account request returns `FAILED_PRECONDITION/ACCOUNT_INACTIVE`.

### FR-3: Scope cost, draft-charge, and export results to authorized tenants/projects

#### TC-FR3-01: Filter account-level provider results to the requested tenant and projects

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-6, IC-12 | critical | automated |

##### Preconditions

- The provider fake returns records for two tenants and several projects under one provider account.
- The caller is authorized for only one tenant and one subset of its projects.

##### Steps

1. Request costs, draft charges, and an export for the authorized tenant.
2. Attempt to request another tenant’s results by changing the tenant ID.

##### Expected Results

- Every returned cost/charge row and export operation contains only records for the authorized tenant and authorized projects.
- The second request returns `PERMISSION_DENIED`; no provider response containing the other tenant’s rows is returned to the caller.

### FR-4: Retain deleted-tenant attribution while revoking access

#### TC-FR4-01: Keep a billing tombstone after tenant deletion

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-8 | critical | automated |

##### Preconditions

- A tenant has an active billing assignment, its M360 account `externalId` matches the tenant ID, and usage events are queued.

##### Steps

1. Delete the tenant.
2. Read the tenant’s billing profile as a tenant user.
3. Allow the queued event to retry through the existing metering adapter after tenant deletion.

##### Expected Results

- The tenant user receives `PERMISSION_DENIED` or `NOT_FOUND` for the deleted tenant.
- The queued event retains its `tenant_id` and is delivered against the linked M360 account's matching `externalId`.
- The assignment is marked read-only/deleted and remains stored until the configured provider-retention cleanup condition is met.

### FR-5: Require coverage for every billable component before publication/provisioning

#### TC-FR5-01: Block publication when a component has no current rate

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- A catalog item contains two billable components; one has a current rate and one has no current rate card.

##### Steps

1. Request pricing resolution for the item.
2. Submit the catalog publication request.

##### Expected Results

- Pricing resolution returns `COVERAGE_GAP` and identifies the uncovered component.
- Publication returns `FAILED_PRECONDITION/COVERAGE_GAP`; the item remains unpublished.

#### TC-FR5-02: Block publication for unsupported formula or explicit no-price row

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- The provider fixture supplies either an unsupported pricing formula or a `NO_PRICE` rate row for a required component.

##### Steps

1. Resolve the catalog item’s pricing.
2. Attempt to publish the item.

##### Expected Results

- Resolution reports `COVERAGE_GAP` with `UNSUPPORTED_FORMULA` or `NO_PRICE` for the affected component.
- Publication is rejected and no estimate is represented as a complete total.

### FR-6: Read draft charges without creating provider financial records

#### TC-FR6-01: Return a stable draft-charge view for repeated reads

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-13 | high | automated |

##### Preconditions

- The provider fake returns a draft-charge view for one tenant and billing period.

##### Steps

1. Read the same tenant/period through the API.
2. Read it again through `osac billing draft-charges`.

##### Expected Results

- Both responses contain the same provider view ID, period, currency, and charge rows.
- The provider fake records zero create or mutate requests.

### FR-7: Export tenant-scoped charges to an external payment system

#### TC-FR7-01: Make charge export tenant-scoped and idempotent

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

##### Preconditions

- The export provider supports the requested tenant-scoped export and the caller is authorized.

##### Steps

1. Submit an export for a tenant and billing period with an idempotency key.
2. Submit the same request again with the same key.

##### Expected Results

- Both responses return the same export operation ID.
- The downstream payment system receives one export containing only the selected tenant’s rows.

### FR-8: Restrict billing and financial operations to billing-specific roles

#### TC-FR8-01: Deny billing mutations to callers without billing-admin permission

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-12 | critical | automated |

##### Preconditions

- A tenant user token has no billing-admin role.

##### Steps

1. Call account link, provider switch, export, and audit-list methods with that token.

##### Expected Results

- Each method returns `PERMISSION_DENIED`.
- No provider mutation or audit-visible successful action occurs.

### FR-9: Record OSAC billing actions for API/CLI audit

#### TC-FR9-01: Verify OSAC audit records for billing actions (audit design pending)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7, IC-13 | high | automated |

##### Preconditions

- A platform billing admin can link an account and request an export.
- The audit model and authorized read surface remain undecided per design §9.4. This case is a behavioral placeholder and is not execution-ready.

##### Steps

1. Link an account and submit an export.
2. Retrieve the resulting audit records through the read surface selected by the audit design.

##### Expected Results

- The selected audit facility records both actions with the actor, operation, affected target, time, and outcome required by the approved audit model.
- Records do not contain provider credentials, raw response bodies, or charge-line payloads.
- Do not assert a billing-specific table, field list, correlation ID, or API route until the audit model is decided.

### FR-10: Keep resource lifecycle available and recover usage across provider outages

#### TC-FR10-01: Preserve resource operations and queued usage during provider outage

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8, IC-10 | critical | automated |

##### Preconditions

- A tenant has running resources and the provider endpoint becomes unavailable.

##### Steps

1. Stop or delete an existing resource.
2. Publish a new billing-enabled item and launch a new resource.
3. Generate usage during the outage, then restore the provider.

##### Expected Results

- Existing resource stop/delete requests complete through the normal lifecycle API.
- New billing-enabled publication and launch return `UNAVAILABLE/BILLING_PROVIDER_UNAVAILABLE`.
- The usage event remains queued or retryable and is accepted once after recovery, with no duplicate provider event.

### FR-11: Install provider credentials through non-plaintext Secret references

#### TC-FR11-01: Render configuration without embedding credentials

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | critical | automated |

##### Preconditions

- Deployment values contain a provider Secret reference and no credential literal.

##### Steps

1. Render the billing charts and inspect generated ConfigMaps, arguments, and Secret references.

##### Expected Results

- Rendered non-Secret resources contain the Secret name/key reference only.
- The credential value appears only in the Secret-backed mount/environment source.

### FR-12: Switch the provider at a billing-period boundary without replaying old usage

#### TC-FR12-01: Route events on either side of the provider switch boundary

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8, IC-9 | high | automated |

##### Preconditions

- M360 is configured before the boundary and another fake adapter is configured for after it.
- Usage events exist immediately before and after the boundary.

##### Steps

1. Apply a provider switch scheduled at the next period boundary.
2. Submit the pre-boundary and post-boundary events.

##### Expected Results

- The pre-boundary event is delivered only to M360.
- The post-boundary event is delivered only to the new provider.
- No pre-boundary event is replayed to the new provider.

### FR-13: Show unhealthy status when usage is not flowing

#### TC-FR13-01: Mark billing health degraded when delivery is stuck

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-10 | high | automated |

##### Preconditions

- The provider adapter has queued events and repeated provider failures.

##### Steps

1. Query `/v1/billing/status` and scrape billing delivery metrics.

##### Expected Results

- Status is `DEGRADED` or `UNAVAILABLE` with an observation timestamp.
- Pending-delivery and failed-request metrics increase; no tenant/account ID appears as a metric label.

### FR-14: Return tenant costs by service/resource and period

#### TC-FR14-01: Filter and group provider costs by service and resource

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- Provider test data contains VMaaS and CaaS cost rows across two billing periods.

##### Steps

1. Query one tenant’s costs for the current period grouped by service and resource.

##### Expected Results

- The response contains only the requested tenant and period, with separate VMaaS/CaaS groups, currency, and `asOf`.

### FR-15: Aggregate costs by nested Project hierarchy

#### TC-FR15-01: Preserve parent/child Project attribution in grouped costs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- A tenant has a parent Project and nested child Project with distinct cost records.

##### Steps

1. Query the tenant’s costs grouped by Project with descendants included.

##### Expected Results

- The response contains separate parent and child Project identifiers, the parent-child relationship, and totals that equal the returned underlying rows.

### FR-17: Return latest calculated charges with `asOf` and scoped access

#### TC-FR17-01: Return provider freshness metadata without exposing another tenant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-12 | high | automated |

##### Preconditions

- Provider test data includes a latest calculation timestamp and rows for an unauthorized tenant.

##### Steps

1. Request current costs as an authorized tenant user.

##### Expected Results

- The response includes the provider’s latest `asOf` timestamp and authorized rows only.
- No rated-transaction or account-balance view is rendered in the first billing UI slice.

### FR-18: Return cost history for accessible resources and Projects

#### TC-FR18-01: Restrict historical cost periods to the caller’s resource/project scope

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-12 | high | automated |

##### Preconditions

- A tenant user can access one Project but not a sibling Project.
- Provider data has cost rows in both Projects over multiple periods.

##### Steps

1. Request historical costs for the parent tenant and selected accessible Project.

##### Expected Results

- The response contains only periods and resources within the authorized Project scope.
- Rows for the inaccessible sibling Project are absent.

### FR-19: List existing provider accounts/status and link an account through OSAC

#### TC-FR19-01: Render normalized account status, association, and disabled-provider state

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-11 | high | manual |

##### Preconditions

- The configured-provider fixture contains active, inactive, linked, and unlinked accounts.
- A second fixture returns `NOT_CONFIGURED` from `/v1/billing/status` and has no provider account data.

##### Steps

1. Open the React provider-admin Billing page as a platform billing admin with the configured-provider fixture and refresh the account list.
2. Load the page with the no-provider fixture.

##### Expected Results

- With a provider configured, the page displays normalized account name, account number when available, active/inactive state, and associated OSAC tenant. Inactive accounts cannot be selected for a new link; no balance or rated-transaction section is present.
- With no provider configured, the page shows a clear disabled state and does not request account or tenant-link data.

### FR-20: Estimate recurring charges using account currency, provider units, and 730 hours/month

#### TC-FR20-01: Calculate and display hourly and monthly recurring estimate

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- The account currency is USD.
- The resolved recurring rate is USD 2.00 per hour and the catalog configuration includes one supported billable item.
- A one-time charge is also present in provider metadata.

##### Steps

1. Request an estimate with no planned start date.
2. Request the same estimate with a specified future start date.

##### Expected Results

- The default response uses today as its effective date; the second response uses the supplied date.
- The recurring total is USD 2.00/hour and USD 1,460/month (`2.00 × 730`).
- The one-time charge is excluded and identified as excluded from the estimate.

#### TC-FR20-02: Preserve a provider-native non-hourly rate unit

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | medium | automated |

##### Preconditions

- A provider fixture returns a supported monthly recurring rate in the tenant account currency.

##### Steps

1. Request an estimate for the configured catalog item.

##### Expected Results

- The response preserves the provider’s monthly unit and amount, and returns the equivalent hourly amount using `monthly ÷ 730`.
- The response does not perform currency conversion.

#### TC-FR20-03: Show estimate freshness and units in the React launch panel

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | manual |

##### Preconditions

- The launch wizard receives an estimate response with hourly and monthly recurring totals, account currency, effective date, and `asOf`.

##### Steps

1. Open the launch wizard for a catalog item with a complete estimate.
2. Change one billable configuration field and wait for the updated estimate response.

##### Expected Results

- The launch panel displays both the per-hour amount and the 730-hour monthly projection in the account currency.
- The updated response date/freshness is shown, and the amount changes to match the selected configuration.

### FR-21: Block new publish/launch for inactive accounts or unresolved/unavailable coverage

#### TC-FR21-01: Reject launch for an inactive linked account

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3, IC-4 | critical | automated |

##### Preconditions

- A tenant has a linked account whose current normalized status is `INACTIVE`.

##### Steps

1. Attempt to launch a resource and publish a billing-enabled catalog item.

##### Expected Results

- Both new operations return `FAILED_PRECONDITION/ACCOUNT_INACTIVE`.
- Existing resource get/stop/delete operations remain available.

#### TC-FR21-02: Reject publish and launch for unresolved component coverage

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3, IC-4 | critical | automated |

##### Preconditions

- A globally visible item has a coverage gap for tenant A's linked account and complete coverage for tenant B's linked account. The operation context identifies the account used for the gate.

##### Steps

1. Attempt publication in tenant A's account context.
2. Attempt a launch as tenant B.

##### Expected Results

- Publication checks tenant A's account and returns `FAILED_PRECONDITION/COVERAGE_GAP` with the component ID and safe reason; it does not check every tenant who may see the global item.
- Tenant B's launch checks only tenant B's linked account and succeeds because that account has coverage.

#### TC-FR21-03: Reject a live gate check when the provider is unavailable

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3, IC-4 | critical | automated |

##### Preconditions

- Account status was previously active, but the live provider endpoint now times out.

##### Steps

1. Submit a publish request.
2. Submit a launch request.

##### Expected Results

- Both requests return `UNAVAILABLE/BILLING_PROVIDER_UNAVAILABLE`.
- The prior status may be shown as stale in the account view but is not accepted as a live price check.

### FR-22: Preserve assignment history through reassignment, suspension, and deletion

#### TC-FR22-01: Preserve assignment history and the existing usage event contract

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2, IC-8 | critical | automated |

##### Preconditions

- Tenant assignment A is effective before timestamp T; assignment B replaces it at timestamp T.
- The existing metering event contains `tenant_id`, and the selected M360 billing account's `externalId` is synchronized to that value.

##### Steps

1. Suspend the tenant, then resume it without changing account assignments.
2. Reassign the account at T and inspect the current and historical assignment records.
3. Verify the existing usage event format remains unchanged and still carries `tenant_id`.
4. Delete the tenant and inspect the retained billing assignment tombstone.

##### Expected Results

- Assignment A closes at T and remains in history for audit; assignment B becomes current.
- Suspension does not change the assignment or deactivate a provider account. Deletion revokes normal tenant access while retaining the billing tombstone.
- The metering event schema has no historical billing-account target. M360 attributes usage using the current `externalId` mapping, so no event-time account attribution is asserted for delayed events.

### FR-23: Enrich VMaaS catalog items with provider pricing

#### TC-FR23-01: VM catalog item includes available pricing

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-14 | high | automated |

##### Preconditions

- The provider fake returns an available price for the VM catalog item's default fields.
- The caller can see the published VM catalog item.

##### Steps

1. Request the VM catalog item through the public catalog API.
2. Inspect the pricing result.

##### Expected Results

- The response contains `pricing.status=AVAILABLE`, the account currency, and the returned VM component amount and unit.

### FR-24: Enrich CaaS catalog items with provider pricing

#### TC-FR24-01: Cluster catalog item includes available pricing

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-14 | high | automated |

##### Preconditions

- The provider fake returns prices for the cluster item's default node-set fields.
- The caller can see the published cluster catalog item.

##### Steps

1. Request the cluster catalog item through the public catalog API.
2. Inspect the pricing components.

##### Expected Results

- The response contains `pricing.status=AVAILABLE` and each resolved cluster billable component.

### FR-25: Resolve catalog pricing against the tenant's effective plan

#### TC-FR25-01: Tenant's linked account plan determines the returned price

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-14 | critical | automated |

##### Preconditions

- Two tenants each have a different linked billing account and effective plan, consistent with the current 1:1 rule.
- The same catalog item is visible to both tenants, and the provider fake returns a distinct amount for each plan.

##### Steps

1. Request the item as a user in tenant A.
2. Request the item as a user in tenant B.

##### Expected Results

- Each tenant receives only the price resolved for its own linked account and effective plan.
- The request does not infer OSAC visibility from provider account membership. Shared-account behavior remains future scope.

### FR-26: Include metered and non-metered components in account base currency

#### TC-FR26-01: Pricing includes all returned components and currency

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-14 | high | automated |

##### Preconditions

- The provider fake returns one metered component and one non-metered component in the account base currency.

##### Steps

1. Request the catalog item.
2. Inspect `pricing.currency_code` and `pricing.components`.

##### Expected Results

- The response contains the account base currency and both components with their amount, unit, and description; no returned component is silently dropped.

### FR-27: Represent unavailable pricing separately from incomplete coverage

#### TC-FR27-01: Provider timeout leaves catalog item browsable without a price

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-14 | critical | automated |

##### Preconditions

- The provider fake times out the catalog-pricing request.

##### Steps

1. Request the catalog list or item.
2. Inspect the catalog response and pricing state.

##### Expected Results

- The catalog request succeeds and includes the item with `pricing.status=UNAVAILABLE` and no fabricated amount.
- The catalog remains browsable; the separate publication/launch gate remains fail-closed under TC-FR21-03.

#### TC-FR27-02: Missing component rate is surfaced as a coverage gap

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3, IC-14 | high | automated |

##### Preconditions

- The provider fake reports no rate for one required billable component.

##### Steps

1. Request the catalog item.
2. Inspect its pricing status and safe message.

##### Expected Results

- The response contains `pricing.status=COVERAGE_GAP` and a non-empty user-safe message; it does not report a complete total.

### FR-28: Expose catalog pricing through API, CLI, and web UI

#### TC-FR28-01: CLI renders component pricing and unavailable state

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-13, IC-15 | high | automated |

##### Preconditions

- The API returns one available catalog item and one unavailable catalog item.

##### Steps

1. Run the existing catalog list/get CLI command in human-readable mode.
2. Run it in machine-readable mode.

##### Expected Results

- Human-readable output includes currency, component units, and an unavailable message; machine-readable output preserves the structured pricing status.

#### TC-FR28-02: Web catalog displays pricing states and keeps items browsable

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-15 | high | automated |

##### Preconditions

- One fixture has billing configured and returns a visible item with `pricing.status=UNAVAILABLE`. A second fixture reports `NOT_CONFIGURED` and returns the same visible catalog item without `pricing`.

##### Steps

1. Open the tenant catalog page with the configured-provider fixture and inspect the item card/detail and launch control.
2. Load the same page with the no-provider fixture.

##### Expected Results

- With a configured but unavailable provider, the item remains visible, its pricing area explains the unavailable price, the UI does not display zero, and launch cannot bypass the live coverage gate.
- With no provider configured, the item remains browsable without a price area or price-dependent launch gate.

### FR-29: Align catalog pricing with visibility and tenant isolation

#### TC-FR29-01: Hidden catalog item and its price are not disclosed

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-12, IC-14 | critical | automated |

##### Preconditions

- A catalog item is visible to tenant A but not tenant B.
- The provider fake has a price for the item.

##### Steps

1. Request the catalog list as tenant A.
2. Request the catalog list as tenant B.

##### Expected Results

- Tenant A receives the item and its price; tenant B receives neither the item nor its price.
- OSAC applies visibility checks before any provider pricing call for tenant B.

### FR-30: Support authorized Cloud Provider Admin preview

#### TC-FR30-01: Provider admin previews only an authorized selected tenant's price

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-12, IC-15 | high | automated |

##### Preconditions

- The caller has Cloud Provider Admin permission for tenant A but not tenant B.
- The provider fake returns distinct prices for both tenants.

##### Steps

1. Request the catalog item using tenant A as the selected preview context.
2. Repeat using tenant B.
3. Repeat as a caller without Cloud Provider Admin permission.

##### Expected Results

- The authorized tenant A request returns tenant A's price.
- Unauthorized tenant selection returns the established authorization error and makes no provider pricing call.

### FR-31: Price the default configuration and signal variability

#### TC-FR31-01: Editable billable field sets price-may-vary

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-14, IC-15 | medium | automated |

##### Preconditions

- The catalog item has an editable billable field.
- The provider fake returns the price for the default configuration.

##### Steps

1. Open the item in the web catalog.
2. Inspect its displayed price and editable field controls.

##### Expected Results

- The displayed amount corresponds to the default field value and the UI displays a price-may-vary indicator.

### FR-32: List OSAC catalog pricing inputs for provider rate-card review

#### TC-FR32-01: Return all distinct billable values and their catalog references

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-16 | high | automated |

##### Preconditions

- Published and draft compute catalog items include locked and editable billable fields.
- An editable field has multiple values available in the same option source used by the catalog UI; some values are used by more than one catalog item.

##### Steps

1. Request the catalog pricing-input inventory as a Cloud Provider Admin.
2. Repeat as a caller without billing-admin authorization.

##### Expected Results

- The authorized response includes each distinct billable dimension/value pair once and lists all catalog items that lock or permit selection of it, including each item's publication state and default/selection mode.
- Editable fields include every value selectable in the catalog flow, not only the configured default.
- The response contains no provider-native rate-card identifiers or coverage claim, and the handler makes no provider call.
- The unauthorized request is denied.

### FR-33: List provider rate-card rules in a UI-friendly normalized format

#### TC-FR33-01: Serialize provider rules as one normalized row per UI line

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-17 | high | automated |

##### Preconditions

- The provider fixture contains currency-specific service rules with wildcard and exact-value predicates, including the Fedora and RHEL examples.
- The OSAC catalog contains one matching item and no item matching at least one provider rule.

##### Steps

1. Request rate-card rows as an authorized Cloud Provider Admin.
2. Inspect the serialized response fields required by the Rates-page row presentation contract.

##### Expected Results

- The response contains one row per provider pricing rule, grouped by normalized service, without expanding wildcard rules into combinations of OSAC catalog values.
- Provider wildcards serialize as `ANY`; exact predicates serialize as `EQUALS` with the value. Each row carries its currency, decimal amount, and provider rate unit.
- Time-based rows may include a 730-hour monthly projection explicitly marked as OSAC-derived; provider-supplied amounts remain marked as provider values.
- Matching catalog items are returned for UI links; an empty match list renders as “Not in catalog.” The row association does not claim complete price coverage.
- Provider-native card/rule IDs, response fields, and raw payloads are absent.

#### TC-FR33-02: Select contract pricing before the default service card

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-17 | high | automated |

##### Preconditions

- A linked account has a contract with distinguishable contract rates and default service-card rates for the same billable configuration.
- A second linked account has no contract and a default service card. The provider fake can separately simulate a failed or ambiguous contract lookup.

##### Steps

1. Request rate-card rows for the account with a contract.
2. Request rate-card rows for the account with no contract.
3. Repeat the first request with a failed contract lookup, then with an ambiguous lookup result.

##### Expected Results

- The account with a contract uses its effective contract pricing path, including only provider-documented inheritance such as M360 contract-service fallback to catalog/list pricing.
- The account with no contract uses the default rate card for the requested service and account currency.
- Failed or ambiguous contract lookup returns an error and never selects the default card by treating the result as confirmed absence.

### NFR-5: Do not persist catalog prices in OSAC

#### TC-NFR5-01: Repeated reads observe provider price changes without OSAC price records

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-14 | high | automated |

##### Preconditions

- The provider fake returns amount A on the first read and amount B on the second read.
- No OSAC catalog-price table or stored price record exists.

##### Steps

1. Read the catalog item and record the amount.
2. Change the provider fake to return amount B.
3. Read the catalog item again.

##### Expected Results

- The second response contains amount B and neither read creates an OSAC database record for the price.

### NFR-6: Keep catalog pricing behind the shared provider boundary

#### TC-NFR6-01: Catalog pricing invokes the shared billing pricing resolver

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3, IC-14 | high | automated |

##### Preconditions

- The shared billing pricing boundary is instrumented with a test spy.
- The catalog server is configured with the M360 provider adapter.

##### Steps

1. Request a priced catalog item.
2. Inspect the calls made by the catalog server and provider client.

##### Expected Results

- The catalog path invokes the shared resolver and does not instantiate a second catalog-specific M360 credential/client path.

### FR-34: Run core fulfillment without a billing provider

#### TC-FR34-01: Preserve catalog and provisioning APIs when billing is disabled

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2, IC-3, IC-4, IC-5, IC-6, IC-9, IC-14, IC-16, IC-17 | critical | automated |

##### Preconditions

- The deployment has no configured billing provider, adapter, or provider credentials.
- A catalog item and target tenant satisfy all normal catalog, authorization, and resource prerequisites.

##### Steps

1. Request `/v1/billing/status`.
2. List and get the catalog item and read the catalog-pricing-input inventory.
3. Publish the item and launch a resource using the normal fulfillment APIs.
4. Call the provider-dependent route families: account discovery/linking and tenant-link view, rate-card rows, pricing resolution, estimates, costs/draft charges, and exports.

##### Expected Results

- Billing status is `NOT_CONFIGURED`; the service starts and core fulfillment APIs remain available.
- Catalog list/get returns the item without a `pricing` field and makes no provider call; the OSAC-only catalog-pricing-input inventory remains readable without one.
- Publication and launch proceed when ordinary OSAC checks pass; the billing coverage gate is skipped.
- Every provider-dependent route family returns `FAILED_PRECONDITION/BILLING_NOT_CONFIGURED`; no request reaches a provider.

### NFR-1: Enforce tenant and Project isolation at every billing boundary

#### TC-NFR1-01: Apply OSAC visibility checks before provider requests

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-12 | critical | automated |

##### Preconditions

- A caller can access one tenant but submits a cost or export request for another tenant.

##### Steps

1. Submit the request with the unauthorized tenant identifier.

##### Expected Results

- The API returns `PERMISSION_DENIED` before a provider query/export call is recorded by the provider fake.

### NFR-2: Preserve duplicate-safe delivery and recovery

#### TC-NFR2-01: Recover after adapter restart without losing or duplicating usage

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8, IC-10 | critical | automated |

##### Preconditions

- A usage event is accepted by the provider, but the adapter restarts before committing its Kafka offset.

##### Steps

1. Restart the adapter and allow it to consume the same offset again.

##### Expected Results

- Provider-side idempotency or the adapter’s deduplication key results in one rated event.
- The Kafka offset advances after the event reaches an accepted or durably quarantined state.

### NFR-3: Keep provider credentials and native financial schema server-side

#### TC-NFR3-01: Redact provider-only fields from public API responses and logs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-4, IC-9, IC-14, IC-15 | critical | automated |

##### Preconditions

- Provider fixtures contain access credentials, `External ID`, contract IDs, rate-card IDs, and a private error body.

##### Steps

1. Call account, estimate, status, and catalog-pricing endpoints.
2. Trigger a provider error and inspect structured logs.

##### Expected Results

- Public responses contain normalized account, price, status, component, and reason fields only; catalog responses omit provider-native service, attribute, contract, and rate-card identifiers.
- Logs contain the correlation ID and normalized failure code but none of the credential, External ID, contract ID, rate-card ID, or response-body values.

### NFR-4: Keep OSAC API behavior provider-neutral

#### TC-NFR4-01: Return the same normalized account, estimate, and rate-row schemas from two adapters

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-3, IC-4, IC-14, IC-17 | high | automated |

##### Preconditions

- A contract test runs against the M360 adapter and a fake second-provider adapter with different native field names and rate units.

##### Steps

1. List accounts, resolve an estimate, price the same catalog configuration, and list rate-card rows through each adapter.

##### Expected Results

- Both adapters return the same OSAC response field names and normalized account, estimate, catalog-pricing, and rate-card-row structures, including wildcard predicates, currency, and rate units.
- Provider-specific request/response fields remain confined to each adapter; unsupported capabilities are explicitly reported.

## Gaps

### Requirement Coverage Gaps

- **FR-16 (PRD invoice-view story):** No provider invoice API or UI is included because the user previously deferred invoice retrieval. The PRD still contains this story. Reconcile the PRD before approval; if invoice viewing remains required, add a normalized invoice endpoint, access rules, and test cases.
- **FR-9 audit implementation:** TC-FR9-01 captures the required outcome, but the audit model, storage, retention, authorization, and read surface remain open in design §9.4. The case is not execution-ready, and no follow-up Jira story exists yet.

All other PRD and user-directed requirements have at least one behavioral test case.

### Interface Change Coverage Gaps

All 17 interface changes have at least one behavioral test case.

### Planning Evidence Matrix — Billing Foundation (OSAC-3784)

The 30 pre-existing OSAC-3784 cases below are retained. Work ownership is a `[DEV]` story under OSAC-3784/3793; decomposition has not created or assigned those stories yet. Commands are the documented component commands. Provider fakes validate OSAC handling of the fake contract only. Unless a row says otherwise, the listed case is planned and has not been run.

| Test case | Owning component / behavior | Tier and owner | Location and command (working directory) | Boundary, prerequisites, and real/faked dependencies |
|---|---|---|---|---|
| TC-FR1-01 | osac-metering: retry and duplicate-safe usage submission | Unit; `[DEV]` story not created | `adapters/`; `make test` (`osac-metering/`) | Adapter/runner code real; provider endpoint faked. Does not run Kafka transport; Kafka integration suite is unavailable under OSAC-4846. |
| TC-FR2-01 | fulfillment-service: account association and 1:1 conflict validation | Component integration; `[DEV]` story not created | `it/`; `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` (`fulfillment-service/`) | Fulfillment Service and database real. Provider account discovery/link verification must be faked; test injection seam is not documented, so this case is not execution-ready until that seam is added. |
| TC-FR3-01 | fulfillment-service: tenant/project-filtered billing reads | Unit; `[DEV]` story not created | Proposed billing server tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | OSAC filters and response projection real; provider account-level rows faked; no live provider. |
| TC-FR4-01 | fulfillment-service: deleted-tenant billing tombstone persistence | Component integration; `[DEV]` story not created | Proposed billing persistence test under `it/`; `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` (`fulfillment-service/`) | Deployed service and database real; provider cleanup/retention faked. No provider deletion boundary is exercised. |
| TC-FR5-01 | fulfillment-service: block publication for a missing rate | Unit; `[DEV]` story not created | Proposed pricing/publish tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | Publication handler and gate real; provider rate lookup faked. Does not prove M360 rate coverage. |
| TC-FR5-02 | fulfillment-service: block unsupported formula or explicit no-price row | Unit; `[DEV]` story not created | Proposed pricing/publish tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | Formula allowlist and gate real; unsupported provider response faked. Formula semantics still require provider validation. |
| TC-FR6-01 | fulfillment-service: stable, read-only draft-charge view | Unit; `[DEV]` story not created | Proposed billing server tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | API projection real; provider response faked and repeated; provider-side non-mutation is not proven by a fake. |
| TC-FR7-01 | fulfillment-service: tenant-scoped idempotent charge export | Unit; `[DEV]` story not created | Proposed export handler tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | Authorization, tenant filtering, and idempotency logic real; payment/provider export faked. Real provider scoping is an open contract gap. |
| TC-FR8-01 | fulfillment-service: billing mutation authorization | Unit; `[DEV]` story not created | Proposed auth/policy tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | OPA/application policy and request path real in process; identities and provider are test fixtures; no live IdP. |
| TC-FR9-01 | OSAC audit facility: record billing actions | Tier/location/owner unresolved pending design §9.4 | No test location or command selected until the audit source, storage, and read contract are defined | Test must exercise the selected durable audit boundary. Provider actions can be faked; current design does not establish a billing-specific table or audit API. No follow-up Jira story is assigned. |
| TC-FR10-01 | fulfillment-service: resource APIs remain available during provider outage | Component integration; `[DEV]` story not created | Proposed API case under `it/`; `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` (`fulfillment-service/`) | Deployed service/database real; billing provider failure injected. Metering queue recovery is a separate required boundary and is not covered by this row. |
| TC-FR10-01 | osac-metering: queued usage is delivered after provider recovery | Component integration; owner/ticket unresolved | No runnable suite/command is documented; OSAC-4846 tracks unavailable Kafka integration infrastructure | Kafka, adapter restart, offsets, and recovery must run for real with a controllable provider. Unit tests with a fake do not prove the transport/recovery boundary. |
| TC-FR11-01 | osac-installer: provider credentials render as Secret references | Helm chart contract/render; `[DEV]` story not created | Proposed chart assertions; `make helm-validate` (`osac-installer/`) | Chart schema/templates render for real; no cluster, provider, or Secret value is deployed. Render assertion must verify plaintext credentials are absent. |
| TC-FR12-01 | osac-metering: route events across the provider switch boundary | Unit; `[DEV]` story not created | `adapters/`; `make test` (`osac-metering/`) | Boundary-selection code real; event timestamps and adapter responses are fixtures. Kafka ordering/offset behavior needs unavailable component-integration coverage under OSAC-4846. |
| TC-FR13-01 | osac-metering: expose degraded delivery health | Unit; `[DEV]` story not created | `adapters/`; `make test` (`osac-metering/`) | Health state/metric code real; stuck delivery simulated. A deployed Prometheus scrape/alert boundary is not covered. |
| TC-FR14-01 | fulfillment-service: normalize cost grouping by service/resource | Unit; `[DEV]` story not created | Proposed cost-query tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | OSAC projection and filtering real; provider cost rows faked; no live provider. |
| TC-FR15-01 | fulfillment-service: preserve nested Project attribution | Unit; `[DEV]` story not created | Proposed cost-query tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | Project hierarchy aggregation real; provider rows and resource visibility are fixtures; database/provider omitted. |
| TC-FR17-01 | fulfillment-service: return latest charges with `asOf` and tenant scope | Unit; `[DEV]` story not created | Proposed cost-query tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | Freshness mapping and tenant filter real; provider timestamps/charges faked. |
| TC-FR18-01 | fulfillment-service: restrict historical costs to visible resources/projects | Unit; `[DEV]` story not created | Proposed cost-query tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | Historical authorization/filter logic real; provider history faked; no live provider. |
| TC-FR19-01 | osac-ui: render account status/association and provider-disabled state | Unit; `[DEV]` story not created | Proposed billing page test under `libs/ui-components/src/pages/provider/`; `pnpm test` (`osac-ui/`) | React view real; configured and `NOT_CONFIGURED` status/account API fixtures. Verifies no account/tenant-link request in disabled mode; no browser deployment, Fulfillment Service, or provider. |
| TC-FR20-01 | fulfillment-service: hourly/monthly estimate using 730 hours | Unit; `[DEV]` story not created | Proposed pricing tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | Decimal arithmetic and projection real; rate inputs faked; no M360 evaluator. |
| TC-FR20-02 | fulfillment-service: preserve non-hourly provider rate unit | Unit; `[DEV]` story not created | Proposed pricing tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | Unit normalization real; provider-native unit supplied by fake adapter. |
| TC-FR20-03 | osac-ui: display estimate freshness and units in launch panel | Unit; `[DEV]` story not created | Proposed launch panel test under `libs/ui-components/src/`; `pnpm test` (`osac-ui/`) | React panel real; estimate API response stubbed. Does not exercise deployed API or provider. |
| TC-FR21-01 | fulfillment-service: reject launch for inactive linked account | Unit; `[DEV]` story not created | Proposed launch handler tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | Launch gate real; account status fake. Deployed service integration is not yet execution-ready for billing configuration. |
| TC-FR21-02 | fulfillment-service: reject publish/launch for unresolved coverage | Unit; `[DEV]` story not created | Proposed pricing/resource handler tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | Gate and resource handler real; missing-rate/formula responses faked. Does not validate the M360 formula inventory. |
| TC-FR21-03 | fulfillment-service: reject live gate when provider is unavailable | Unit; `[DEV]` story not created | Proposed pricing/resource handler tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | Live-check decision real; timeout injected at provider interface. Catalog list/get outage behavior is separately covered by TC-FR27-01. |
| TC-FR22-01 | fulfillment-service/osac-metering: preserve assignment history and existing usage event contract | Unit/contract; `[DEV]` story not created | Proposed assignment tests under `fulfillment-service/internal/` (`ginkgo run -r internal`) and existing adapter contract tests under `osac-metering/adapters/` (`make test`) | Local tests verify assignment intervals, tombstone behavior, current `externalId` synchronization, and the unchanged `tenant_id` event format. They do not exercise live M360 routing; user-confirmed behavior is that M360 uses the current `externalId`, so event-time attribution is not asserted. |
| TC-FR34-01 | fulfillment-service: operate core catalog/resource APIs without billing | Component integration; `[DEV]` story not created | Fulfillment API suite; `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` (`fulfillment-service/`) | Fulfillment Service and database run for real with no provider adapter or credentials. Verify status, catalog, publish/launch, pricing-input inventory, each provider-dependent route family returning `BILLING_NOT_CONFIGURED`, and absence of provider calls. |
| TC-NFR1-01 | fulfillment-service: authorize tenant/project before provider calls | Unit; `[DEV]` story not created | Proposed auth/query tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | OSAC auth/filter path and provider-call spy real in process; identity and provider responses faked. |
| TC-NFR2-01 | osac-metering: recover after restart without loss/duplication | Component integration; owner/ticket unresolved | No runnable Kafka-backed suite/command is documented; see OSAC-4846 | Requires real Kafka offsets/restart/flush behavior and controllable provider. `make test` unit coverage is not sufficient for this boundary. |
| TC-NFR3-01 | fulfillment-service: redact provider fields in API and logs | Unit; `[DEV]` story not created | Proposed serialization/logging tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | OSAC redaction and response serialization real; credentials/native fields/private errors are synthetic fixtures. |
| TC-NFR4-01 | fulfillment-service: normalized contract across provider adapters | Unit contract; `[DEV]` story not created | Proposed adapter contract tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | M360 adapter plus a fake second provider run against one contract; this proves contract normalization, not a production second-provider integration. |

### Planning Evidence Matrix — Catalog Pricing (OSAC-3793)

The rows below identify the required tier and boundary for the newly integrated catalog-pricing behaviors. `[DEV] OSAC-3784/OSAC-3793 implementation story` means the story has not yet been created or assigned; no Jira key is available. Commands are repository-defined unless marked as a proposed location. Provider fakes do not establish real M360 contract behavior.

| Test case | Owning component / behavior | Tier and owner | Location and command (working directory) | Boundary, prerequisites, and real/faked dependencies |
|---|---|---|---|---|
| TC-FR23-01 | fulfillment-service: VM catalog price enrichment | Unit; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | `internal/servers/`; `ginkgo run internal/servers` (`fulfillment-service/`) | Real handler and normalization code; provider response faked through the billing pricing interface; database and M360 omitted. |
| TC-FR24-01 | fulfillment-service: cluster catalog price enrichment | Unit; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | `internal/servers/`; `ginkgo run internal/servers` (`fulfillment-service/`) | Real handler and cluster-field mapping code; provider response faked; database and M360 omitted. |
| TC-FR25-01 | fulfillment-service: resolve against the authenticated tenant's linked account | Unit; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | `internal/servers/`; `ginkgo run internal/servers` (`fulfillment-service/`) | Real tenant/account selection logic; two distinct tenant accounts and provider plans faked; shared-account behavior is outside the current 1:1 scope. |
| TC-FR26-01 | fulfillment-service: normalize metered/non-metered components and currency | Unit; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | `internal/servers/`; `ginkgo run internal/servers` (`fulfillment-service/`) | Real response mapping; provider component rows faked; no live provider or database. |
| TC-FR27-01 | fulfillment-service: contain provider timeout on catalog reads | Unit; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | `internal/servers/`; `ginkgo run internal/servers` (`fulfillment-service/`) | Real catalog response behavior; timeout injected at the provider boundary; deployment and M360 omitted. |
| TC-FR27-02 | fulfillment-service: distinguish missing component coverage | Unit; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | `internal/servers/`; `ginkgo run internal/servers` (`fulfillment-service/`) | Real aggregate pricing status; missing-rate response faked; live provider omitted. TC-FR21-02 separately covers publish/launch rejection. |
| TC-FR28-01 | fulfillment-service CLI: human and machine-readable catalog output | Component integration; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | `it/`; `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` (`fulfillment-service/`) | Deployed Fulfillment Service, database, and CLI run for real. A configurable billing pricing fake is a prerequisite not currently established by the suite; M360 is not run. The command is defined, but this scenario is not execution-ready until that test seam exists. |
| TC-FR28-02 | osac-ui: catalog price, unavailable, and disabled-state rendering | Unit; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | Proposed `libs/ui-components/src/pages/tenant/CatalogPage.test.tsx`; `pnpm test` (`osac-ui/`) | React catalog components run for real; configured-provider `UNAVAILABLE` and `NOT_CONFIGURED` API responses are fixtures. Fulfillment Service, database, provider, and browser deployment are omitted. No persisted UI E2E suite exists. |
| TC-FR29-01 | fulfillment-service: catalog visibility before provider pricing | Unit; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | `internal/servers/`; `ginkgo run internal/servers` (`fulfillment-service/`) | Real authorization/visibility path; provider spy verifies no call for hidden items; database/provider faked or omitted. |
| TC-FR30-01 | fulfillment-service: selected-tenant preview authorization | Unit; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | `internal/servers/`; `ginkgo run internal/servers` (`fulfillment-service/`) | Real public-server authorization path; caller claims and provider spy controlled in test; no live identity provider or M360. |
| TC-FR31-01 | osac-ui: default-config price and price-may-vary indicator | Unit; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | Proposed `libs/ui-components/src/pages/tenant/CatalogPage.test.tsx`; `pnpm test` (`osac-ui/`) | React rendering runs for real; catalog item and pricing response are fixtures; provider and deployed API omitted. |
| TC-FR32-01 | fulfillment-service: aggregate billable values across catalog items | Unit; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | Proposed server tests under `internal/servers/`; `ginkgo run internal/servers` (`fulfillment-service/`) | Real aggregation and authorization logic; catalog and selectable-value sources are fixtures. Provider is omitted; the test verifies no provider call occurs. |
| TC-FR33-01 | fulfillment-service: normalize provider rule data as Rates UI rows | Unit; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | Proposed adapter/handler tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | Real normalization and row mapping; M360 and second-provider payloads are fixtures with different wildcard/currency/unit encodings; no live provider. |
| TC-FR33-02 | fulfillment-service: apply contract-first/default-card pricing selection | Unit/adapter contract; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | Proposed pricing adapter contract tests under `internal/`; `ginkgo run -r internal` (`fulfillment-service/`) | Real selection/error handling; contract, no-contract, failed, and ambiguous lookup outcomes are supplied by provider fakes. Does not prove M360 live lookup semantics. |
| TC-NFR5-01 | fulfillment-service: read-time price without OSAC price persistence | Unit; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | `internal/servers/`; `ginkgo run internal/servers` (`fulfillment-service/`) | Real handler path over two reads; provider fake changes the returned amount; repository/database assertions verify no catalog-price write. |
| TC-NFR6-01 | fulfillment-service: use shared billing pricing boundary | Unit; `[DEV] OSAC-3784/OSAC-3793 implementation story` (not created) | `internal/servers/`; `ginkgo run internal/servers` (`fulfillment-service/`) | Real catalog handler and injected resolver spy; provider client is faked; verifies no second M360 client is created. |

### Boundary and execution gaps

- A full browser-to-Fulfillment-to-provider pricing journey has no persisted UI E2E suite. The API component-integration target is known, but its billing-provider injection seam is not documented. Owner and follow-up Jira URL are unresolved; create/assign QE work during decomposition.
- The available public M360 documentation does not establish the prospective catalog evaluator, OSAC-to-provider billable-field mapping, or formula compatibility. Unit tests with provider fakes do not validate those provider boundaries. The owner is the billing/provider integration team; no follow-up Jira ticket or real-provider test command is recorded yet.
- Coverage is checked only for the account in the gated action's context; a globally visible catalog item does not require coverage from every tenant, and each tenant launch uses that tenant's linked account (design §4.3; TC-FR21-02).

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 47 |
| Critical | 20 |
| High | 25 |
| Medium | 2 |
| Low | 0 |
| Automated | 45 |
| Manual | 2 |
| Requirements with test cases | 39 / 40 |
| Interface changes with test cases | 17 / 17 |
