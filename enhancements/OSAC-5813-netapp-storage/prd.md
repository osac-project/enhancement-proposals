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
Manual NetApp configuration prevents tenants from using NetApp-backed VM disks
and independent volumes without provider intervention. The Developer Preview
extends the existing storage lifecycle to these consumers while preserving
tenant isolation. CaaS consumption and Enclave installation follow later.

## In Scope

- **VMaaS:** NetApp-backed boot and additional disks over SCSI/FC, using existing
  storage-tier selection and VM lifecycle workflows.
- **VaaS:** independently provisioned NetApp volumes, attached to authorized VMs
  through the shared attachment workflow.
- **Shared administration:** NetApp backend registration and block tiers through
  the existing OSAC UI, CLI, and API; automatic isolated tenant onboarding,
  readiness and failure visibility, and guarded offboarding.
- **Installation and documentation:** supported installer deployment, ONTAP
  privileges and host/HBA/zoning prerequisites, and consumption, retention,
  and recovery guidance.

These are Developer Preview requirements, in descending priority. Later delivery
adds CaaS consumption and configurable, validated NetApp installation settings
through the Enclave Wizard; neither blocks the preview.

| Service | Milestone | Required consumption outcome |
|---|---|---|
| VMaaS | Developer Preview | A VM uses the selected NetApp tier for boot or additional disks. |
| VaaS | Developer Preview | An independent volume is attached to an authorized VM through the shared attachment workflow. |
| CaaS | Post Developer Preview | NetApp-backed StorageClasses appear automatically; a PVC supports workload reads and writes. |

Each tenant receives an isolated ONTAP storage virtual machine (SVM) with central
credentials and authorized-consumer access. Tenants receive no ONTAP management
credentials.

When a tenant has both VAST and NetApp tiers, existing tier-selection rules apply:
each volume uses its selected tier's provider. Existing VAST volumes remain usable.

Registration validates management access; FC consumption requires connected-host
verification. Failed onboarding leaves storage not ready. Failures remain
visible until recovery; diagnostics exclude credentials and other tenants' details.

Offboarding follows [OSAC-23's lifecycle](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-23-tenant-storage-onboarding/prd.md)
and [OSAC-2117's isolation safeguards](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-2117-pure-storage-flashblade/prd.md):
consumer cleanup precedes backend cleanup, and removing one VM preserves
other consumers. Remaining workload volumes, including retained volumes, or
unresolved attachments block SVM removal; detachment alone does not authorize
data deletion. Completion is
reported only after owned tenant storage resources and credential entries are
removed and the tenant's previous credentials no longer grant access. Cleanup
failures remain visible and block completion until recovery succeeds.
Later CaaS delivery applies the same safeguards to cluster removal.

Direct attachment follows [OSAC-4884](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-4884-volume-api-storage-attach-detach/prd.md),
including authorization, access capabilities, retries, and deletion guards.
In-place OSAC upgrades remain unsupported.

### Required verification

QE-owned automated E2E tests exercise deployed OSAC with an FC-capable ONTAP
array and connected hosts. Manual experiments supplement this acceptance evidence.

- The VMaaS and VaaS paths above demonstrate successful workload I/O.
- Tenant A cannot attach, read, or delete Tenant B's volumes through supported
  workflows; its own volumes remain usable.
- Representative management-access, SVM-onboarding, and FC-attachment failures
  report the affected operation and safe diagnostics. Correction and retry
  succeed without duplicate tenant storage allocation.
- VM removal preserves other consumers. Offboarding is blocked while
  workload volumes or attachments remain; subsequent cleanup removes owned
  resources and access.
- A tenant's VAST and NetApp tiers both work and honor provider selection.

CaaS workload I/O and cluster cleanup are acceptance requirements for later
CaaS delivery. Wizard input validation and a usable NetApp-enabled deployment
are acceptance requirements for later Enclave delivery.

## Out of Scope

- BMaaS storage integration, reserved for a separate feature.
- NFS, iSCSI, FCoE, and NVMe/TCP transports.
- Migration between NetApp and other providers.
- Performance benchmarking or custom QoS beyond native Trident capabilities.
- New NetApp-specific credential rotation or expiry-renewal automation.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want documented ONTAP privileges and
  host/HBA/zoning prerequisites and installation settings, so that I can prepare
  FC infrastructure and deploy NetApp storage through the supported installer.
- As a Cloud Infrastructure Admin, I want FC validation and attachment failures
  to identify the affected operation and host with safe diagnostic detail, so
  that I can investigate fabric or host configuration.
- **Post Developer Preview:** As a Cloud Infrastructure Admin, I want to
  configure and validate NetApp installation settings through the Enclave Wizard,
  so that I can deploy the integration through the supported Wizard workflow.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want backend registration to report management
  connectivity or credential-validation failures, so that I can correct access
  before tenant onboarding.
- As a Cloud Provider Admin, I want NetApp block tiers with native performance
  policies, so that tenants can select my storage offerings.
- As a Cloud Provider Admin, I want automatic isolated SVM onboarding with
  actionable privilege/resource-limit failures and safe retries, so that I can
  enable tenant storage without manual provisioning or duplicate allocations.
- As a Cloud Provider Admin, I want removal to preserve other consumers and
  offboarding completion to confirm removal of owned resources and access, so
  that workloads remain usable and tenant state cannot leak into later assignments.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to select an assigned NetApp tier for
  VM boot and additional disks, including when VAST tiers are also assigned, so
  that my VM uses the intended provider without separate disk provisioning.
- As a Tenant Admin or Tenant User, I want to provision an independent
  NetApp-backed volume and later attach it to an authorized VM through the
  shared attachment workflow, so that its lifecycle is independent of compute.
- As a Tenant Admin or Tenant User, I want pending or failed volume
  attachment and mount operations to show progress and a safe failure reason
  through the existing UI, CLI, and API status views, so that I can recognize
  unusable storage and seek provider assistance.
- **Post Developer Preview:** As a Tenant Admin or Tenant User, I want ready
  NetApp-backed StorageClasses and visible PVC failures on my CaaS cluster, so
  that I can run stateful workloads without manual storage configuration.

## Assumptions

- Infrastructure administrators supply supported FC-connected hosts, prepared
  zoning, and sufficient ONTAP privileges.
- Existing central credential handling applies; this feature adds onboarding and
  removal integration rather than a new credential-rotation policy.

## Dependencies

**Developer Preview — VMaaS and VaaS:**

- Shared Volume API integration with VM disk creation and cleanup
  ([OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037)), plus
  [OSAC-4884](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-4884-volume-api-storage-attach-detach/prd.md)
  for independent-volume attachment. VM creation alone does not deliver VaaS
  attachment.
- A supported NetApp/Trident FC path from
  [OSAC-5807](https://redhat.atlassian.net/browse/OSAC-5807), with an FC-capable
  array and connected VM hosts available for QE. Investigation proceeds in
  parallel; working FC I/O and automated acceptance gate preview delivery.
- Existing Core/secrets support for central credentials and the OSAC installer
  deployment path.

**Post Developer Preview:** CaaS additionally requires
[OSAC-1332](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1332-caas-cluster-storage/prd.md)
and supported OSAC CSI/Trident delivery to workload clusters. Enclave installation
additionally requires installer schema support, Enclave plugin adoption, and
verified Wizard controls; that chain gates the later Wizard capability.

## Risks

- An unproven FC path can delay the target milestone; a supported contingency
  remains open in OQ-1.
- Missing FC test access prevents the required automated acceptance evidence
  even if management-path work succeeds (OQ-2).
- VM lifecycle integration does not supply independent-volume attachment;
  delays to OSAC-4884 can block the VaaS preview path.

## Open Questions

| ID | Question | Status / owner | Impact |
|---|---|---|---|
| OQ-1 | What supported FC alternative or milestone adjustment applies if OSAC-5807 cannot establish the required path in time? | Open — Storage Working Group / Feature owner | No fallback has been agreed; FC delivery remains gated. |
| OQ-2 | Which FC array and connected hosts will QE use, and when will approved access be available? | Open — Storage Working Group / partner workstream / QE | Determines readiness for automated FC acceptance. |
| OQ-3 | Which NetApp-specific retained-volume and partial-cleanup recovery procedure satisfies the shared offboarding contract, including cleanup timing and credential removal? | Open — Storage Working Group / Core-secrets workstream | Completes operational recovery guidance while preserving deletion guards; no NetApp-specific grace period is established. |

---

## Provenance

Authored: draft @ prd 0.11.3 - 2bd6607, workspace main @ c5819927b
Final: respond @ prd 0.11.3 - 2bd6607, workspace osac-5813-netapp-integration @ c8d0d8890

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"c8d0d8890","source_repo_branch":"osac-5813-netapp-integration","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
