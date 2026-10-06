# Tenant Onboarding and Offboarding for NetApp ONTAP Storage

| Field | Value |
|---|---|
| Author(s) | Zoltan Szabo |
| Jira | [OSAC-5813](https://redhat.atlassian.net/browse/OSAC-5813) |
| Date | 2026-10-05 |
| Last updated | 2026-10-06 |
| Target milestone | OSAC 0.4 — Developer Preview (VMaaS integration) |

## Problem Statement

Cloud Provider Admins already onboard tenants to VAST-backed storage through
OSAC, but lack the same automated tenant onboarding/offboarding for NetApp ONTAP
over Fibre Channel (FC). Providers need isolated tenant storage configuration
and clear lifecycle status so that the shared VMaaS workflow can consume their
NetApp tiers in the Developer Preview.

## In Scope

- Register one ONTAP backend and one or more FC block tiers through the existing
  UI, CLI, and API.
- Automatically onboard tenants into separate storage virtual machines (SVMs),
  each with its own management LIF (logical interface), centrally managed
  credentials and usable storage configuration for its assigned tiers.
- Offboard tenant storage using the established lifecycle safeguards.

Installation and infrastructure preparation may use documented CLI steps.
Offboarding follows
[OSAC-23](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-23-tenant-storage-onboarding/prd.md),
[OSAC-2117](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-2117-pure-storage-flashblade/prd.md)
and their data/dependency guards; completion confirms removal of owned tenant
SVM/LIF configuration and credentials, with previous access invalidated.
Tenants receive no ONTAP management credentials.

### Required verification

Onboard two tenants and verify distinct SVMs and management LIFs, correct tier
bindings, and FC access limited to authorized consumers. FC requires no separate
tenant IP data LIF; its target LIFs and access configuration follow ONTAP's FC
model. Failed onboarding remains not ready and retries avoid duplicate resources.
Offboarding respects data/dependency guards, removes owned resources and access,
and preserves the other tenant's storage. QE validates the resulting configuration
through the shared VMaaS-over-FC flow; VM disk lifecycle implementation is a
separate dependency below. Setup and acceptance may be performed manually.

## Out of Scope

- Shared VM/Volume lifecycle implementation, independent VaaS volumes and dynamic attach/detach.
- OSAC CSI integration changes or removal, and vendor-driver installation automation.
- CaaS and BMaaS storage integration, and Enclave.
- Multi-cluster or multi-backend preview deployment profiles.
- FC switch configuration, zoning, host/HBA preparation, and dedicated fabric diagnostics.
- NFS, iSCSI, FCoE, and NVMe/TCP transports.
- Migration between NetApp and other providers; supported in-place OSAC upgrades.
- Performance benchmarking or custom QoS beyond native provider capabilities.
- New NetApp-specific credential rotation or expiry-renewal automation.
- Allocation from a pool of pre-created SVMs.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want backend registration to report management
  connectivity or credential-validation failures, so that I can correct access
  before tenant onboarding.
- As a Cloud Provider Admin, I want multiple NetApp block tiers with native
  performance policies on the registered backend, so that tenants can select
  my storage offerings.
- As a Cloud Provider Admin, I want automatic isolated SVM and management LIF
  onboarding with safe, actionable privilege/resource-limit failures and retries, so that I can
  enable tenant storage without duplicate allocations.
- As a Cloud Provider Admin, I want tenant offboarding to report completion or
  safe, actionable failures under existing dependency guards, so that I can
  recover cleanup and prevent tenant state leaking into subsequent assignments.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want my assigned NetApp tiers to become
  available after onboarding, so that I can use the existing VMaaS workflow
  without handling ONTAP management credentials.

## Assumptions

- One existing, connected OpenShift cluster with OpenShift Virtualization hosts
  OSAC and tenant VMs. The preview profile operates without the OSAC CSI driver;
  existing CSI integrations remain intact.
- Infrastructure administrators supply workers with supported FC access, prepared
  zoning, management connectivity, and the required vendor storage deployment.
  These prerequisites use documented setup steps.
- OSAC receives permission and credentials to create tenant SVMs and management
  LIFs. Confirmation for target deployments is pending (OQ-4).
- Management access or SVM creation does not prove FC connectivity; infrastructure
  owners complete any zoning needed for newly created tenant targets.
- Existing central credential handling and lifecycle safeguards apply.

## Dependencies

- Existing Core/secrets support and configuration/onboarding handoffs.
- [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037) owns the shared
  VM/Volume lifecycle, including disk creation, ownership and cleanup. This
  feature supplies tenant/tier storage configuration; the consumption handoff
  needs agreement with that workstream (OQ-1).
- QE and infrastructure owners supply an FC-capable array and connected workers.
  Access details have been handed to the E2E team; successful FC consumption
  remains to be verified (OQ-2). Relevant findings from
  [OSAC-5807](https://redhat.atlassian.net/browse/OSAC-5807) may inform FC setup.
- Independent VaaS/attachment remains a platform stretch goal under separate
  work, including [OSAC-4884](https://redhat.atlassian.net/browse/OSAC-4884).

## Risks

- Management-only array access or workers without FC connectivity cannot establish
  VM consumption acceptance (OQ-2).
- Missing SVM/LIF creation permissions prevent automatic onboarding; pre-created
  SVM assignment requires a different agreed model (OQ-4).
- A mismatch with the shared consumption configuration can block VM acceptance
  despite successful tenant resource creation (OQ-1).

## Open Questions

| ID | Question | Status / owner | Impact |
|---|---|---|---|
| OQ-1 | Which tenant/tier configuration does the shared VM consumption path require, and who owns any NetApp-specific adaptation? | Open — Feature owner / OSAC-6037 workstream | Defines the onboarding output without duplicating shared VM lifecycle implementation. |
| OQ-2 | Has the intended NetApp environment demonstrated working FC consumption from its OpenShift workers? | Access handed to E2E team; validation pending — QE / infrastructure owners | Establishes readiness for joint VM acceptance. |
| OQ-3 | Which partial-onboarding and failed SVM/LIF/credential cleanup recovery steps satisfy existing safeguards? | Open — Storage Working Group / Core-secrets workstream | Defines safe recovery and offboarding completion without data loss or duplicate allocation. |
| OQ-4 | Will target deployments provide privileges for OSAC to create tenant SVMs and management LIFs? | Open — Infrastructure/partner workstream / Feature owner | Required for create-on-onboard; pre-created SVM pooling is not an agreed fallback. |

---

## Provenance

Authored: draft @ prd 0.11.3 - 2bd6607, workspace main @ c5819927b
Final: revise @ prd 0.11.3 - 2bd6607, workspace osac-5813-netapp-integration @ c8d0d8890

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"c8d0d8890","source_repo_branch":"osac-5813-netapp-integration","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","respond","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
