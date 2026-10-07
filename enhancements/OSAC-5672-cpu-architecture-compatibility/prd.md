# Validate CPU architecture compatibility

| Field | Value |
|-------|-------|
| Author(s) | Nick Carboni |
| Jira | [OSAC-5672](https://redhat.atlassian.net/browse/OSAC-5672) |
| Date | 2026-10-06 |

## Problem Statement

Tenants can wait for a bare-metal deployment that cannot succeed because the selected DiskImage does not support the hardware architecture. Today, Tenant Admins and Tenant Users can submit BareMetalInstance requests through a BareMetalInstanceCatalogItem, selecting a DiskImage and a BareMetalInstanceType, but OSAC does not check their architecture compatibility before provisioning. DiskImage and BareMetalInstanceType catalogs also use inconsistent names for the same architecture, such as `amd64` and `x86_64`. Without a common vocabulary and early compatibility checks, providers maintain ambiguous catalogs and tenants encounter avoidable provisioning failures.

## In Scope

- BMaaS: prevent incompatible DiskImage and BareMetalInstanceType selections from starting bare-metal provisioning, including selections supplied through BareMetalInstanceCatalogItem or BareMetalInstanceTemplate defaults. Compatibility uses the effective selected resources after defaults and references are resolved.
- Canonical architecture names are `amd64`, `arm64`, and `s390x`. UI, CLI, and API architecture input, display, filters, and validation use this vocabulary consistently for DiskImages and BareMetalInstanceTypes. [Clarify: R1.Q1]
- Only exact canonical architecture names are accepted. Aliases such as `x86_64` and `aarch64`, case variations such as `AMD64`, values with surrounding whitespace, and unknown names are rejected with an actionable error listing the accepted canonical names. Inputs are not normalized. [User]
- A DiskImage is architecture-compatible when its declared supported architectures include the selected BareMetalInstanceType's canonical architecture. DiskImages supporting several architectures remain usable for each matching BareMetalInstanceType. A mismatch returns a stable, actionable error before provisioning starts, identifying the incompatible selection and how the caller can correct it.
- Compatibility enforcement applies to new provisioning and BareMetalInstance changes that would trigger provisioning. Changes that do not trigger provisioning, including metadata edits and stop requests, remain possible despite architecture incompatibility, subject to existing authorization and lifecycle rules. [Clarify: R1.Q4]
- Existing BareMetalInstanceTypes with noncanonical architecture values remain visible; new provisioning using those BareMetalInstanceTypes is blocked until a Cloud Provider Admin corrects the architecture to an exact canonical name. Existing catalog data must be prepared for canonical-only validation; legacy spellings are not accepted for provisioning. OSAC does not currently support in-place upgrades. [User]
- After a BareMetalInstanceType is selected in the UI, architecture-incompatible DiskImages remain visible but disabled with a reason. Compatible DiskImages remain selectable, including multi-architecture DiskImages. CLI and API requests receive the same authoritative compatibility protection. [Clarify: R1.Q5]
- Existing tenant visibility and DiskImage lifecycle checks remain enforced. Compatibility messages expose only resources and catalog information the caller is permitted to see; they do not expose infrastructure details.
- User documentation explains the canonical vocabulary, rejected noncanonical inputs, DiskImage compatibility, and correction of legacy values. It identifies the architecture-bearing resources reviewed and the paths that cannot yet enforce compatibility. Regression verification covers exact canonical inputs, rejected aliases, case and whitespace variations, multi-architecture matches, rejected mismatches, BareMetalInstanceCatalogItem and BareMetalInstanceTemplate defaults, legacy correction, and BareMetalInstance changes that do not trigger provisioning across the affected UI, CLI, and API workflows. [User]

## Out of Scope

- Inspecting OCI manifests or disk-image contents to determine architecture automatically.
- CPU feature or model compatibility beyond architecture.
- Enforcing DiskImage architecture compatibility for VMaaS; VM hardware selection does not currently declare CPU architecture, and that capability requires a separate Feature.
- Validating provider inventory architecture unless it becomes a declared OSAC resource contract.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want DiskImages and BareMetalInstanceTypes to display the same canonical architecture names so that the global catalogs are reliable and reusable.
- As a Cloud Provider Admin, I want to identify existing BareMetalInstanceType architectures that require correction to canonical names so that I can restore those BareMetalInstanceTypes to use for new provisioning. [User]

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want a BareMetalInstance request selecting an incompatible DiskImage and BareMetalInstanceType to be rejected before provisioning starts so that it does not cause an avoidable infrastructure failure.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want compatible DiskImages to remain selectable for my chosen BareMetalInstanceType so that I can submit a request that passes architecture validation, including when a DiskImage supports multiple architectures. [Clarify: R1.Q5]
- As a Tenant Admin or Tenant User, I want an incompatible DiskImage to show why it is disabled in the UI so that I can correct my selection before submission. [Clarify: R1.Q5]
- As a Tenant Admin or Tenant User, I want an incompatible CLI or API request to return an actionable error before provisioning starts so that I can correct the DiskImage and BareMetalInstanceType selection without waiting for a failed deployment or seeing infrastructure details.
- As a Tenant Admin or Tenant User, I want to edit metadata or stop an existing BareMetalInstance when its architecture metadata is incompatible so that I can manage it without triggering new provisioning. [Clarify: R1.Q4]

---

## Provenance

Authored: revise @ prd 0.11.3 - 2bd6607, workspace main @ df80256d8
Phases: draft, revise, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"df80256d8","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
