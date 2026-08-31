# Region-based Billing

| Field       | Value   |
|-------------|---------|
| Author(s)   | Moti Asayag |
| Jira        | https://redhat.atlassian.net/browse/OSAC-3798 |
| Date        | 2026-08-31 |

This feature extends the Billing Integration MVP (OSAC-3784), which most
requirements below build on; that issue is the anchor for the billing adapter,
invoicing, and permission model referenced throughout.

## Problem Statement

Sovereign cloud deployments operate across regulatory jurisdictions with
different tax rules, e-invoicing mandates (for example EU ViDA and India GST),
and compliance requirements. Today a Cloud Provider Admin has no way to record
which jurisdiction a tenant belongs to, so every tenant's charges and invoices
are treated identically regardless of where the tenant is billed. Without a
per-tenant jurisdiction, the provider cannot produce jurisdiction-compliant
invoices or apply the correct tax and e-invoicing treatment, which blocks
billing in any market that mandates it.

## In Scope

- A billing region is a per-tenant billing/tax attribute — it applies to the
  whole tenant, not to individual resources.
- A billing region is mandatory for every new tenant and captured during
  onboarding.
- Tenants created before this feature acquire a billing region through day-2
  administrator assignment; no automated migration is performed [Clarify: R2.Q2].
- Defining billing regions, assigning or changing a tenant's billing region, and
  viewing a tenant's billing region are each available via the API, CLI, and UI
  [Clarify: R2.Q3].
- OSAC provides predefined jurisdiction templates that a provider can adopt
  as-is, customize, or extend with new billing regions [Clarify: R1.Q2].
- A billing-region change takes effect for future billing periods only;
  already-issued invoices are not re-rated [Clarify: R1.Q3].
- The feature works with whichever billing platform the deployment uses; it does
  not depend on a specific platform choice [Clarify: R1.Q4].
- Existing tenant-onboarding documentation is updated to reflect the new
  mandatory billing-region selection step [Jira: OSAC-3798].

## Out of Scope

- Per-resource billing region assignment — billing region is per-tenant
  [Jira: OSAC-3798].
- A tax calculation engine — tax rules are configured per billing region, not
  computed [Jira: OSAC-3798].
- Generating jurisdiction-compliant e-invoice documents (for example EU ViDA XML
  or India GST files). OSAC applies each tenant's billing-region tax and
  e-invoicing treatment to its charges and invoices; the deployment's billing
  platform produces the final compliant document [Clarify: R1.Q1].
- Any relationship between a tenant's billing region and where its resources
  physically run (compute placement, availability zones, network topology).
  Billing region is purely a billing/tax attribute [Clarify: R3.Q2].

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to define the list of available billing
  regions — starting from OSAC's predefined jurisdiction templates or authoring
  my own — each carrying its tax jurisdiction, e-invoicing format, and
  regulatory framework, so that tenant onboarding presents the correct billing
  options [Clarify: R1.Q2].
- As a Cloud Provider Admin, I want to assign a billing region to each tenant
  when I onboard it, by selecting from the defined list, so that the tenant is
  billed under the correct jurisdiction from its first billing period
  [Clarify: R2.Q1].
- As a Cloud Provider Admin, I want to set or change a tenant's billing region
  after onboarding — including assigning one to tenants that predate this
  feature — so that subsequent invoices reflect the correct jurisdiction when a
  tenant's circumstances change [Clarify: R1.Q3, R2.Q2].
- As a Cloud Provider Admin, I want each tenant's charges and invoices to reflect
  the tax jurisdiction and e-invoicing format of that tenant's billing region,
  so that I can produce jurisdiction-compliant invoices without configuring each
  tenant by hand [Clarify: R1.Q1].
- As a Cloud Provider Admin, I want defining billing regions and assigning them
  to tenants to be restricted to users holding billing permissions, so that only
  authorized personnel can change how tenants are billed [Clarify: R2.Q4].
- As a Cloud Provider Admin, I want billing-region administrative actions
  (defining a region, and assigning or changing a tenant's region) to produce
  audit log entries, so that I can satisfy compliance and regulatory audit
  requirements [Jira: OSAC-3784].

### Tenant Admin

- As a Tenant Admin, I want my organization's billing region to be visible in my
  account details, so that I understand which billing regulations apply to my
  invoices [Jira: OSAC-3798].

## Assumptions

- The deployment's billing platform consumes the tax jurisdiction, e-invoicing
  format, and regulatory framework carried by a tenant's billing region and uses
  them to render jurisdiction-compliant invoices. If a chosen platform cannot
  consume this treatment, the compliance outcome this feature enables is not
  realized [Clarify: R1.Q1, R1.Q4].
- The Billing Integration MVP (OSAC-3784) provides an audit log for
  billing-administrative actions that billing-region actions can record into
  [Jira: OSAC-3784].

## Dependencies

- **Billing Integration MVP (OSAC-3784):** Provides the pluggable billing
  adapter, tenant-to-billing-account lifecycle, invoice generation, and the
  billing permission model that billing-region administration relies on. A
  tenant's billing-region treatment is applied to the charges and invoices this
  pipeline produces, so the relevant billing output must exist before this
  feature is observable end-to-end.
- **Billing platform choice (OSAC-3048):** The M360-vs-Koku decision is
  unresolved. This feature is platform-agnostic and does not block on it, but
  the chosen platform is what renders the final jurisdiction-compliant invoice.

---

## Provenance

Authored: draft @ prd 0.9.0 - a17a43d, workspace HEAD @ ed93971

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"a17a43d","source_repo":"ed93971","source_repo_branch":"HEAD","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
