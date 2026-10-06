# Tenant Onboarding for NetApp ONTAP Storage

| Field | Value |
|---|---|
| Author(s) | Zoltan Szabo |
| Jira | [OSAC-5813](https://redhat.atlassian.net/browse/OSAC-5813) |
| Date | 2026-10-05 |
| Last updated | 2026-10-06 |
| Target milestone | OSAC 0.4 — Developer Preview (VMaaS and VaaS) |

## Problem Statement

Cloud Provider Admins already onboard tenants to VAST-backed storage through
OSAC, but NetApp ONTAP over Fibre Channel (FC) lacks an automated integration.
Providers must configure tenant storage manually. The Developer Preview
automates backend/tier registration and isolated tenant onboarding for VMaaS
and VaaS. Remaining deployment and consumption steps may be manual.

## In Scope

Developer Preview MVP:

- Register ONTAP backends and FC block tiers through the existing UI, CLI, and API.
- Automatically onboard tenants into isolated SVMs with centrally managed
  credentials and configuration usable for their assigned tiers.
- Support VMaaS boot/additional disks and independent VaaS volumes over SCSI/FC;
  Trident setup, fabric preparation, volume provisioning and attachment may
  use documented manual steps during the preview.

Attachment and offboarding follow the same safeguards as other providers:
[OSAC-23](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-23-tenant-storage-onboarding/prd.md),
[OSAC-2117](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-2117-pure-storage-flashblade/prd.md)
and [OSAC-4884](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-4884-volume-api-storage-attach-detach/prd.md).
These apply to manual operations too. Tenants receive no ONTAP management credentials.

### Required verification

Verify backend/tier registration, isolated onboarding, failure visibility and
safe retries; failed onboarding remains not ready. Demonstrate FC I/O for a
NetApp-backed VM disk and an independent volume on prepared hosts. Manual
acceptance is sufficient for the preview; fully automated E2E is not a delivery gate.

## Out of Scope

- CaaS and BMaaS storage integration.
- Enclave Wizard integration.
- FC switch configuration, zoning, host/HBA preparation, and dedicated
  fabric diagnostics.
- Fully automated installation and end-to-end consumption as preview requirements.
- NFS, iSCSI, FCoE, and NVMe/TCP transports.
- Migration between NetApp and other providers.
- Performance benchmarking or custom QoS beyond native Trident capabilities.
- New NetApp-specific credential rotation or expiry-renewal automation.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want backend registration to report management
  connectivity or credential-validation failures, so that I can correct access
  before tenant onboarding.
- As a Cloud Provider Admin, I want NetApp block tiers with native performance
  policies, so that tenants can select my storage offerings.
- As a Cloud Provider Admin, I want automatic isolated SVM onboarding with
  actionable privilege/resource-limit failures and safe retries, so that I can
  enable tenant storage without manual provisioning or duplicate allocations.
- As a Cloud Provider Admin, I want tenant storage configuration and any remaining
  manual steps to be clear, so that I can enable VMaaS/VaaS consumption without
  exposing management credentials or weakening existing lifecycle safeguards.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to select an assigned NetApp tier for
  VM boot and additional disks, including when VAST tiers are also assigned, so
  that my VM uses the intended provider, with provider assistance permitted
  during the preview.
- As a Tenant Admin or Tenant User, I want to provision an independent
  NetApp-backed volume and attach it to an authorized VM, with provider assistance
  permitted during the preview, so that its lifecycle is independent of compute.

## Assumptions

- Infrastructure administrators supply supported FC-connected hosts, prepared
  zoning, sufficient ONTAP privileges, and the required Trident deployment.
- Successful management access or SVM onboarding does not prove FC connectivity;
  infrastructure owners complete any zoning needed for newly created tenant targets.
- Existing central credential handling applies; this feature adds onboarding and
  reuses existing credential lifecycle safeguards.

## Dependencies

- Existing Core/secrets support and provider/operator/AAP configuration handoffs
  for backend/tier registration and tenant onboarding.
- A supported NetApp/Trident FC consumption path, investigated in
  [OSAC-5807](https://redhat.atlassian.net/browse/OSAC-5807), with an FC-capable
  array and connected VM hosts for acceptance. Configuration/onboarding work
  proceeds in parallel with this investigation.
- [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037) supplies shared VM disk
  lifecycle integration; OSAC-4884 supplies independent-volume attachment.
  Completing these automated consumption paths is not a prerequisite for
  backend/tier registration and onboarding; documented manual steps are permitted.

## Risks

- An unproven FC path or unavailable FC test access can prevent demonstrating
  consumption even when registration and onboarding work (OQ-1/OQ-2).
- Manual setup and cleanup require a clear operational handoff that preserves
  tenant isolation and retained data (OQ-3).

## Open Questions

| ID | Question | Status / owner | Impact |
|---|---|---|---|
| OQ-1 | Which supported FC consumption path will be used for preview acceptance? | Open — Storage Working Group / Feature owner | Establishes the manual or automated path used to demonstrate VMaaS/VaaS. |
| OQ-2 | Which FC array and connected hosts are available, and when will approved access be ready? | Open — Storage Working Group / partner workstream / QE | Determines readiness for manual FC acceptance. |
| OQ-3 | Which manual setup, retained-volume and partial-cleanup recovery steps remain after onboarding? | Open — Storage Working Group / Core-secrets workstream | Defines the operational handoff while preserving existing deletion and credential safeguards. |

---

## Provenance

Authored: draft @ prd 0.11.3 - 2bd6607, workspace main @ c5819927b
Final: revise @ prd 0.11.3 - 2bd6607, workspace osac-5813-netapp-integration @ c8d0d8890

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"c8d0d8890","source_repo_branch":"osac-5813-netapp-integration","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","respond","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
