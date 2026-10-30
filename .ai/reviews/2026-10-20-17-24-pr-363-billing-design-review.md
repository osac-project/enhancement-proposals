# Review: PR #363 — OSAC Billing Integration and Catalog Pricing (OSAC-3784 / OSAC-3793)

Scope: cross-validate (1) your stated understanding, (2) PRD OSAC-3784 + PRD OSAC-3793,
(3) `design.md`/`testplan.md` in PR #363, and (4) the actual `osac-project/osac` codebase.
Report only — no code or PR comments produced.

Sources: PR #363 (sha `47762b75`, design.md 345 lines, testplan.md 1211 lines), both linked PRDs,
the full PR review-comment thread (65 comments), and a shallow clone of `osac-project/osac` main
(`fulfillment-service`, `osac-metering`, `proto/public`).

---

## 1. Your understanding vs. the PRDs

| Your point | Verdict |
|---|---|
| UI shows a price estimate per catalog item (tenant admin / cloud admin view) | **Matches** PRD-3793. Minor nuance: PRD scopes the *browsing* story to Tenant Admin/User; the Cloud Provider Admin only gets a **preview-as-a-tenant** view, not an independent admin price list. |
| UI shows an estimate at provisioning/launch time (tenant user) | **Partially matches, with a real conflation.** PRD-3784's Tenant User story ("view the estimated cost of the resources I have deployed") is about **already-deployed** resources — it shows the billing system's latest *calculated* charge, not a pre-submit estimate. The design adds a separate `PriceEstimates.Create` ("prospective estimate for a selected configuration before you submit it"), which the design itself labels **"an additional agreed design capability... distinct from the PRD's latest-calculated-cost view."** Neither PRD actually asked for a pre-launch "what would this cost me" estimator — the design team added it. Worth deciding if that's wanted/correct, since it's scope the PRD didn't request. |
| Which billing provider is attached to OSAC, shown to Cloud Platform Admin | **Matches** (`BillingProviderStatuses.Get`). |
| Each tenant has a correlation ID in the billing provider, usable to filter/identify entries | **Conflicts with the design, and the design doesn't come from the PRD on this point either.** §4.3/§4.5 state provider-native account references (M360 `externalId`) are **never returned to any client, including Cloud Provider Admins** — only an OSAC-generated opaque `billing_account.id` is exposed. If an admin ever needs to cross-reference an OSAC tenant against the M360 console (support case, reconciliation), there is currently no sanctioned way to do that through any OSAC API. This isn't raised anywhere in the 65-comment review thread — it looks like a genuinely open gap. |
| Fulfillment API queries the billing provider for rate cards (price per unit per service type) | **Matches exactly** (`ProviderRateCardItems.List`, pricing-resolution algorithm in §4.1). |
| Estimates use a constant 30-day month | **Does not match the design, and neither PRD specifies a month length at all.** The design (and testplan) use a **730-hour** month: `USD 2.00/hour × 730 = USD 1,460/month` (testplan.md TC-FR20-01). 730 hours is the standard average-month convention (365×24/12), **not** 720 hours (a flat 30 days). If your mental model was 720h, every monthly figure the design produces will be ~1.4% higher than you'd expect. This is purely a design-team convention choice — worth confirming you're fine with 730h specifically, since it's the thing closest to "wrong" in your framing. |
| Rate-card ID/name must map to OSAC's service-type/atomic-resource naming; UI/CLI can list curated atomic resources per service type to validate the mapping | **Matches closely** (`CatalogPricingInputs.List` — "list metered billable dimensions and all default/selectable values... with the items that use or offer each value," explicitly for checking "provider rate-card completeness"). |
| PR defines the design + new endpoints + I/O schemas, no code | **Matches** — documentation-only PR, 2 files, 1,556 lines added, zero implementation. |

---

## 2. PRD → Design scope deltas

The review thread (masayag as PRD author, CodeRabbit, and your own comments from today) already surfaces most of the real conflicts. I'm sorting them by status so you know what's genuinely still open vs. already settled, plus two items nobody has raised yet.

### Already raised and resolved/accepted
- **BMaaS scope-creep** — an earlier design revision accidentally covered BMaaS gating; `amito` removed it (10-15 comment, "Removing this in the upcoming commit-set"). Current design.md correctly excludes BMaaS (OSAC-3795) throughout. ✅ Closed.
- **Provider-switch support** — PRD's Cloud Infrastructure Admin story wants config-based provider switching (M360→Koku); design explicitly makes this unsupported this milestone. `amito` agreed explicitly (10-15: "I will state that explicitly in §4.6/§2.2"), and current design.md §2.2/§4.6 do so. This is an accepted PRD deviation, but **the PRD text itself hasn't been amended** to reflect the deferral — just a documentation-hygiene gap, not a design problem.
- **Day-one account-creation ambiguity** — masayag asked the design to "specify the day-one path" (10-13); current design.md §4.1 now has an explicit "Day-one account path" section. The *ambiguity* is resolved, but see below — the underlying contradiction is not.

### Still open / unresolved as of the latest revision
- **1:N vs. 1:1 tenant-to-account.** PRD-3784's glossary and multiple Cloud Provider Admin stories (shared-account scoping, shared-account deletion) assume one billing account can back several tenants. The design hard-codes 1:1 for this milestone because M360 issues one `externalId` per account, and frames 1:N as "a follow-up." masayag pushed back hard on 10-13 ("Either amend the PRD to 1:1 for this provider... or specify a real shared-account attribution model"), and you independently objected today to justifying this via one provider's limitation rather than keeping the design provider-agnostic. **No resolution visible in the thread.** This is the single biggest unresolved scope conflict — it removes an entire PRD user story, not just a field.
- **Non-metered billable components.** Both PRDs are emphatic that paid add-ons, bundled licenses, and setup fees must be priced and gated exactly like metered dimensions — it's in PRD-3784's core coverage-gate story and PRD-3793's display requirement ("itemizes any non-metered billable component charges"). The design scopes `CatalogPricingInputs.List`, the coverage-gate table, and the catalog pricing example to **metered only**, calling non-metered "deferred" with no tracking reference. masayag flagged this twice (gating, 10-13; display, same day on §2.1 line 47) and CodeRabbit flagged it again on 10-19 against the testplan's "40 of 40 requirements covered" claim. **No reply from `amito` addressing it either way.** This is the second-biggest open gap, and unlike 1:N it doesn't even have a stated rationale — it just isn't mentioned as a cut.
- **Account auto-creation contradiction.** PRD-3784's Assumptions state: "When billing integration is enabled on a deployment with existing tenants, billing accounts are created for those tenants." The design's Day-one path says the opposite: OSAC never creates accounts; a Cloud Provider Admin must create each one in M360 and then manually run `TenantBillingAssignments.Create` per tenant — "Enabling billing does not auto-create an account or assignment per existing tenant." Clarifying the *mechanism* (which masayag asked for) didn't reconcile this — the PRD assumption is still factually wrong against the design as written. One of the two documents needs to change.
- **Audit logging.** PRD-3784 has an explicit Cloud Provider Admin story requiring OSAC audit-log entries for billing-provider install/switch, tenant-to-account linking, and draft-invoice retrieval/export. The design defers all of it to an unspecified future "platform audit feature" (§2.2 Non-Goal), and the PR's own "Requesting Review On" list names this as open (§9.3) — so at least it's self-flagged, not hidden. masayag's suggested resolution stands unaddressed: "If audit stays out of this feature, say so in the PRD and drop it from acceptance here." PRD text is still unchanged.
- **Draft invoices / invoice reads / exports** — PRD-3784 has detailed Cloud Provider Admin and Tenant Admin stories for all three. Design keeps them in the API table as placeholders but implements none of them this increment. Not contentious in the thread, but it means a large fraction of PRD-3784's stories are simply not in this design at all.

### Not raised by anyone yet (new from this review)
- **Provider-native ID never exposed, anywhere** (see §1 above) — worth asking whether that's actually operationally workable for support/reconciliation.
- **Nested-project cost roll-up.** PRD's Tenant Admin story wants costs aggregated "by Project (including nested Projects)." The design's `BillingCosts.List` groups by project ID and filters visibility but never describes whether nested-project costs roll up into the parent total or are returned flat for the caller to sum. Small, but worth a one-line clarification before implementation starts.
- **Usage-health story satisfied by a different surface than the PRD implies.** PRD's Cloud Infrastructure Admin wants to "see when billing integration is unhealthy (usage is not flowing)." The design explicitly keeps `usage_delivery_state` as `UNKNOWN` on the new `BillingProviderStatuses.Get` API and tells the admin to use existing metering Prometheus metrics instead. Reasonable technically, but means the PRD story is fulfilled by infrastructure the admin has to separately know about, not by the API surface the story names.

---

## 3. Design vs. current `osac` codebase — feasibility

Checked against a shallow clone of `osac-project/osac` main (`fulfillment-service`, `osac-metering`, `proto/public`):

| Design claim | Status | Evidence |
|---|---|---|
| "Fulfillment and metering may share one M360 HTTP helper" | **Real client exists; the bug the design calls out is real too.** `osac-metering/adapters/m360/client.go` is a working M360 HTTP client (bearer auth, 30s timeout, retry classification) that only does usage submission today — no account/pricing/cost queries. It currently embeds raw response bytes into error messages, exactly matching the design's own admission that "the current metering adapter putting response bytes into errors is a required fix when that helper is shared" (§4.8). |
| "M360 maps `tenant_id` through the account's current `externalId`" | **Not implemented anywhere today.** No `externalId`/account-mapping code exists in `osac-metering`; `tenant_id` passes straight through unchanged. The `TenantBillingAssignments` reconciliation flow (§4.2) is a wholly new write path, not a wrapper on existing logic. |
| New billing proto services | **Absent.** Zero billing/pricing protos across `proto/public` and `proto/private` (72 existing `.proto` files checked). |
| Catalog Items v2 field governance (OSAC-3538) — a hard PRD-3793 dependency | **Already present.** `field_policy_type.proto` / `field_definition_type.proto` implement editable/locked field semantics, and `compute_instance_catalog_item_type.proto` already imports them. This dependency is satisfied, not a blocker. |
| `billing_account` / `tenant_billing_assignment` persistence | **No schema yet, but the pattern is mature.** `fulfillment-service/internal/database/migrations` already has 133 sequential numbered `.up.sql` Postgres migrations plus a DAO layer — mechanical fit, not a new subsystem. |
| Per-method OPA allow-list | **Matches reality exactly.** `internal/auth/policies/authz.rego` already gates every method by literal gRPC path (e.g. `grpc_method == "/osac.public.v1.Projects/List"`). New billing methods slot in the same way. |
| CleanAPI REST-from-proto | **Confirmed real** (`proto/buf.gen.yaml`). |
| `instance_type` as the VMaaS billable dimension (your own PR comment, and masayag's 10-13 comment) | **Independently confirmed correct by code.** `osac-metering`'s `ComputeInstanceBillingDimensions` already sends `instance_type`, `image_ref`, `boot_disk_size_gib` to M360 today. The design's own rate-card JSON example uses `"service": "compute_instance"` as the matched dimension instead of `instance_type` — your objection and masayag's are both backed by what's actually shipping in metering right now, not just a style preference. |

**Bottom line:** nothing in the design fights the existing architecture — persistence, OPA, proto/CleanAPI, and the OSAC-3538 dependency are all already in place and idiomatic. The one concrete pre-existing bug the design surfaces (M360 client leaking response bodies into errors) is real and verified, not hypothetical.

---

## Open questions carried into your review

1. **1:1 vs 1:N** — is the PRD's shared-account scenario formally dropped for this milestone (PRD amendment + follow-up Jira), or does the design need to solve it?
2. **Non-metered components** — deliberate MVP cut or an oversight? It currently has no stated rationale anywhere, unlike every other cut in this design.
3. **Account auto-creation** — PRD assumption vs. design behavior directly disagree; which one is actually correct operationally?
4. **730-hour month** — confirm you're fine with 730h specifically (not 720h/30-day), since it changes every number shown to users by ~1.4%.
5. **Provider-native ID exposure** — if an admin can never see the M360 `externalId` through any OSAC surface, how do they cross-reference a tenant in M360's own console for support?

Not covered in depth: `testplan.md`'s 48 test cases (beyond spot-checking the 730-hour example and the FR/NFR-vs-REQ/AC labeling question masayag already answered you on). Flagging this as a scope choice, not an oversight — say if you want a second pass on it against the same gaps above.

---

## 4. Testplan deep-dive (full 48-case read)

Read the whole 1,211-line `testplan.md` against the three open PRD conflicts above, plus anything else notable.

### The three named gaps, as reflected in the testplan

- **1:N vs. 1:1** — the testplan doesn't just stay silent on this, it actively locks in 1:1 as a tested invariant. FR-2's title is literally "...current 1:1 rule..."; `TC-FR2-01` asserts that linking an **already-linked** account to a second tenant must fail with `ACCOUNT_ALREADY_BOUND`; `TC-FR25-01` says "Shared-account behavior remains future scope." **If this testplan is approved as-is, approving it is implicitly also approving dropping 1:N for this increment** — there's no way to sign off on these test cases and still expect shared-account support to land alongside them. That raises the stakes on resolving the open 1:N question before testplan sign-off, not after.
- **Non-metered components** — same pattern. `FR-26` states outright: "Non-metered add-ons, licenses, and setup fees are **deferred**." `TC-FR26-01` explicitly requires that non-metered rows "must not be required for coverage." But here's the sharper finding: the testplan's own **"Gaps" section never lists this as a gap.** It lists FR-9 (audit), FR-6/7/16 (draft charges/exports/invoices), and FR-12 (provider switch) as known deferrals — but not the non-metered-component scope cut, even though it's a clear, named PRD requirement (PRD-3784 coverage story, PRD-3793 display requirement) that isn't met. The testplan's "40 of 40 requirements covered" claim is true only because the requirement set itself was narrowed to metered-only, silently, without that narrowing appearing in the document's own gap tracker.
- **Account auto-creation** — no test case anywhere exercises "enabling billing on a deployment with existing tenants auto-creates accounts for them" (the PRD assumption). Every account-related precondition (`TC-FR2-01`, `TC-FR19-01`, etc.) starts from "a Cloud Provider Admin can access an **existing** provider account" — i.e., manual creation is baked in as given, not tested as a design decision. Like the point above, this isn't listed in the "Gaps" section either. Two of your three named conflicts are present by *omission* from a document that claims complete requirement coverage.

### New findings from the full read

- **`/v1/billing/status` DEGRADED contradiction is still unresolved.** `TC-FR13-01` ("FR-13: Show unhealthy status when usage is not flowing") expects `/v1/billing/status` to report `DEGRADED`/`UNAVAILABLE` when delivery is stuck. `design.md` §7 explicitly says the opposite: *"Do not set this RPC to DEGRADED because usage delivery is stuck; fulfillment has no metering lag signal in this design."* masayag flagged exactly this contradiction on 10-13 ("Say whether that status includes metering health..."). It is **still contradictory in the latest revision** (same sha as everything else reviewed here) — nobody has reconciled the test case with the design text yet.
- **The `externalId`/correlation-ID question is already being locked in by a test, not left open.** `TC-NFR3-01` is an explicit negative test asserting logs and public responses contain "none of the credential, External ID, contract ID, rate-card ID, or response-body values." This isn't just design-doc phrasing anymore — approving this testplan makes "admins can never see the provider-native ID anywhere" a tested contract. If question 5 from the open-questions list matters to you, it needs resolving **before** this testplan is approved, since reversing it later means deleting/rewriting a committed negative test.
- **Nested-Project rollup is actually more specified in the testplan than in the design.** `TC-FR15-01` requires "totals that equal the returned underlying rows" for parent/child Project costs — the design doc never describes this rollup arithmetic at all. This is a design.md documentation gap rather than a testing gap (correcting my earlier read) — worth asking that §4.3's `BillingCosts.List` description be updated to match what the test plan already commits to.
- **Two CRITICAL test cases are currently unexecutable, not just unscheduled.** `TC-FR10-02` (queued usage delivered after provider recovery) and `TC-NFR2-01` (no usage loss/duplication across adapter restart) are both priority `critical`, and both are blocked on Kafka integration test infrastructure that doesn't exist yet (`OSAC-4846`, "no runnable suite/command is documented"). These are exactly the two cases that guarantee no billing usage is lost or double-counted — arguably the most important reliability property in the whole design — and they currently have no path to being run at all, independent of implementation effort.
- **The test-count mismatch CodeRabbit flagged on 10-19 is still present.** Line 6 says "Total test cases: 49"; the Summary table at the bottom still says "Total test cases: 48." Trivial, but it means the document hasn't been touched since that comment landed.
- **Process note, not a defect:** masayag's answer to your FR/NFR question is confirmed by the document itself — "FR/NFR labels in this testplan are local grouping labels, not PRD identifiers" (line 10). This testplan does not do REQ-ID/AC-level traceability the way your own test-plan gate requires; that's an OSAC-project convention difference, not something wrong with this specific document.

### Net effect on your review

Of your three named conflicts, the testplan doesn't resolve any of them — it operationalizes two (1:1, non-metered-deferral) as tested facts while hiding that narrowing from its own gap tracker, and simply never touches the third (auto-creation). Combined with the still-open `/v1/billing/status` contradiction and the two unexecutable critical reliability tests, I'd treat the testplan as **not ready to approve independently of the design** — its gaps section undersells how much is actually deferred or contradicted, and two load-bearing reliability tests can't run yet for infrastructure reasons outside this PR's control.
