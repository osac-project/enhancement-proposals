# Associate a tenant with its identity in the external billing system

| Field     | Value                                                              |
|-----------|--------------------------------------------------------------------|
| Author(s) | Orli Nagar                                         |
| Jira      | [OSAC-6161](https://redhat.atlassian.net/browse/OSAC-6161)        |
| Date      | October 13, 2026                                                   |

## Problem Statement

OSAC meters tenant resource consumption and reports it to external billing systems.
There is currently no supported way for a Cloud Provider Admin to record, at tenant
onboarding time, the identity a tenant holds in an external billing system. Whoever
operates the external billing system must maintain a mapping between OSAC tenant
identifiers and external accounts manually, outside the platform. This mapping is
undocumented, error-prone, and must be rebuilt each time a tenant is onboarded —
causing misattributed or unbillable consumption until an operator corrects it by hand.

## In Scope

- A Cloud Provider Admin can supply an opaque external billing identifier for a tenant
  at creation time via the Fulfillment API and read it back on the tenant resource.
- The external billing identifier is provider-controlled and inaccessible to Tenant
  Admins and Tenant Users through any interface.
- For a tenant with a recorded external billing identifier, consumption OSAC
  reports for that tenant can be located under the corresponding account in the
  external billing system, for every metered resource type.
- Changing a tenant's external billing identifier takes effect going forward:
  consumption OSAC reports after the change is attributed to the new identifier,
  and consumption already reported under the previous identifier is unchanged.

## Out of Scope

- Console UI for setting or reading the identifier — a future increment.
- Associating a tenant with more than one external billing system or account.
- Verifying that a supplied identifier corresponds to a real account in the external
  billing system — OSAC has no access to the external system at onboarding time.
- Onboarding automation that sources the identifier from an external system
  automatically.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to record an external billing identifier for a
  tenant when I create that tenant via the Fulfillment API, so that consumption is
  attributed to the correct billing account from the start.
- As a Cloud Provider Admin, I want to read the external billing identifier on a
  tenant via the Fulfillment API, so that I can confirm the tenant is correctly
  linked to the billing system before it starts consuming resources.
- As a Cloud Provider Admin, I want to create a tenant without providing an external
  billing identifier, so that tenants not billed through an external system are not
  blocked from onboarding.
- As a Cloud Provider Admin, I want the external billing identifier to be inaccessible
  to Tenant Admins and Tenant Users through any interface, so that billing account
  details are not disclosed to tenants.
- As a Cloud Provider Admin, I want to change a tenant's external billing
  identifier after creation, so that consumption is attributed to the correct
  account when the tenant's billing account changes.

---

## Provenance

Authored: respond @ prd 0.11.5 - 1c6e8de, workspace main @ f0a8211
Phases: draft, respond, respond, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"f0a8211","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
