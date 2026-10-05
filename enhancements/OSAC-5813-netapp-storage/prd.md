# Tenant Onboarding for NetApp ONTAP Storage

| Field | Value |
|---|---|
| Author(s) | Zoltan Szabo |
| Jira | [OSAC-5813](https://redhat.atlassian.net/browse/OSAC-5813) |
| Date | 2026-10-05 |
| Target milestone | OSAC 0.4 — Tech Preview |

## Problem Statement

Cloud Provider Admins already onboard tenants to VAST-backed storage through
OSAC, but NetApp ONTAP over Fibre Channel (FC) lacks an automated integration.
Manual NetApp configuration prevents the same self-service experience for
clusters, virtual machines, and independently provisioned volumes. This feature
extends the existing storage lifecycle to NetApp while preserving tenant
isolation.

## In Scope

- SCSI over FC storage for CaaS, VMaaS, and VaaS through existing tier-selection
  and service-specific consumption workflows.
- NetApp backend registration and FC tiers through the existing OSAC UI, CLI,
  and API, including management-access validation and native performance policies.
- Automatic tenant onboarding with a dedicated ONTAP storage virtual machine
  (SVM), central credentials, and access limited to authorized consumers.
  Tenant users receive no ONTAP management credentials.
- Required NetApp installation settings are configurable and validated through
  the Enclave Wizard.
- Administrator documentation covers ONTAP privileges, supported hosts/HBAs,
  zoning prerequisites, Enclave installation, and failure recovery. Tenant
  documentation covers consumption, status, and retention.

| Service | Required consumption outcome |
|---|---|
| CaaS | NetApp-backed StorageClasses appear automatically; a PVC supports workload reads and writes. |
| VMaaS | A VM uses the selected NetApp tier for boot or additional disks. |
| VaaS | A volume is provisioned independently of compute and later attached to an authorized VM through the shared attachment workflow. |

When a tenant has both VAST and NetApp tiers, existing tier-selection rules apply:
each volume uses its selected tier's provider. Existing VAST volumes remain usable.

Registration validates ONTAP management access. FC consumption is verified on
connected hosts; failures remain visible until the affected operation succeeds.
Diagnostics exclude credentials and details about other tenants.

Offboarding follows [OSAC-23's lifecycle](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-23-tenant-storage-onboarding/prd.md)
and [OSAC-2117's isolation safeguards](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-2117-pure-storage-flashblade/prd.md):
cluster cleanup precedes backend cleanup, and removing one cluster preserves
other consumers. Remaining workload volumes, including retained volumes, or
unresolved attachments block SVM removal; detachment alone does not authorize
data deletion. Completion is
reported only after owned tenant storage resources and credential entries are
removed and the tenant's previous credentials no longer grant access. Cleanup
failures remain visible and block completion until recovery succeeds.

Direct attachment follows [OSAC-4884](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-4884-volume-api-storage-attach-detach/prd.md),
including authorization, access capabilities, retries, and deletion guards.
In-place OSAC upgrades remain unsupported.

### Required verification

QE-owned automated E2E tests exercise deployed OSAC with an FC-capable ONTAP
array and connected hosts. Manual experiments supplement this acceptance evidence.

- All three consumption paths above demonstrate successful workload I/O.
- Tenant A cannot attach, read, or delete Tenant B's volumes through supported
  workflows; its own volumes remain usable.
- Representative management-access, SVM-onboarding, and FC-attachment failures
  report the affected operation and safe diagnostics. Correction and retry
  succeed without duplicate tenant storage allocation.
- Cluster removal preserves other consumers. Offboarding is blocked while
  workload volumes or attachments remain; subsequent cleanup removes owned
  resources and access.
- A tenant's VAST and NetApp tiers both work and honor provider selection.
- The Enclave Wizard rejects invalid required inputs and accepts a valid
  configuration that produces a usable NetApp-enabled deployment.

## Out of Scope

- BMaaS storage integration, reserved for a separate feature.
- NFS, iSCSI, FCoE, and NVMe/TCP transports.
- Migration between NetApp and other providers.
- Performance benchmarking or custom QoS beyond native Trident capabilities.
- New NetApp-specific credential rotation or expiry-renewal automation.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want documented ONTAP privileges and
  host/HBA/zoning prerequisites, so that I can prepare and verify FC
  infrastructure before enabling NetApp storage.
- As a Cloud Infrastructure Admin, I want FC validation and attachment failures
  to identify the affected operation and host with safe diagnostic detail, so
  that I can investigate fabric or host configuration.
- As a Cloud Infrastructure Admin, I want to configure and validate NetApp
  installation settings through the Enclave Wizard, so that I can deploy the
  integration through the supported installation workflow.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want backend registration to report management
  connectivity or credential-validation failures, so that I can correct access
  before tenant onboarding.
- As a Cloud Provider Admin, I want NetApp FC tiers with native performance
  policies, so that tenants can select my storage offerings.
- As a Cloud Provider Admin, I want isolated tenant SVMs onboarded automatically,
  so that tenant storage needs no manual array provisioning.
- As a Cloud Provider Admin, I want failed SVM creation, including privilege or
  ONTAP resource-limit failures, to leave storage not ready with an actionable reason,
  so that I can correct the problem and retry without duplicate allocations.
- As a Cloud Provider Admin, I want cluster removal to preserve other consumers,
  so that their storage remains usable.
- As a Cloud Provider Admin, I want offboarding completion to confirm removal of
  owned resources and access under the shared lifecycle safeguards, so that
  tenant data or credentials cannot leak into subsequent assignments.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to select an assigned NetApp tier,
  including when VAST tiers are also assigned, so that my workload uses the
  intended storage provider.
- As a Tenant Admin or Tenant User, I want to provision an independent
  NetApp-backed volume and later attach it to an authorized VM through the
  shared attachment workflow, so that its lifecycle is independent of compute.
- As a Tenant Admin or Tenant User, I want usable storage for the consumption
  scenarios above, so that my workloads can persist data.
- As a Tenant Admin or Tenant User, I want pending or failed volume/PVC
  attachment and mount operations to show progress and a safe failure reason
  through the existing UI, CLI, and API status views, so that I can recognize
  unusable storage and seek provider assistance.

## Assumptions

- Infrastructure administrators supply supported FC-connected hosts, prepared
  zoning, and sufficient ONTAP privileges.
- Existing central credential handling applies; this feature adds onboarding and
  removal integration rather than a new credential-rotation policy.

## Dependencies

- **Shared storage contracts:** OSAC-23, OSAC-2117,
  [OSAC-1332 CaaS storage](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1332-caas-cluster-storage/prd.md),
  and OSAC-4884 supply the lifecycle, isolation, authorization, retention, and
  attachment baseline. Delivery of each consumption path depends on its shared
  capabilities; NetApp-specific recovery details remain in OQ-3.
- **Trident FC path:** The Storage Working Group's
  [OSAC-5807 investigation](https://redhat.atlassian.net/browse/OSAC-5807) must
  establish a supported FC path. Research proceeds in parallel with requirements
  work, but successful FC consumption gates feature delivery.
- **Credentials:** The Core/secrets workstream supplies secure central storage
  and delivery to authorized integration components.
- **Enclave installation:** Feature delivery is blocked until required NetApp
  settings can be configured and validated in the Wizard with supported
  installer and Enclave versions.
- **QE infrastructure:** The Storage Working Group, partner workstream, and QE
  must provide an FC-capable array and connected hosts.
  [EPMB-1595](https://redhat.atlassian.net/browse/EPMB-1595) supports ONTAP Select
  management experiments; Select cannot supply FC acceptance evidence.

## Risks

- An unproven FC path can delay the target milestone; a supported contingency
  remains open in OQ-1.
- Missing FC test access prevents the required automated acceptance evidence
  even if management-path work succeeds (OQ-2).

## Open Questions

| ID | Question | Status / owner | Impact |
|---|---|---|---|
| OQ-1 | What supported FC alternative or milestone adjustment applies if OSAC-5807 cannot establish the required path in time? | Open — Storage Working Group / Feature owner | No fallback has been agreed; FC delivery remains gated. |
| OQ-2 | Which FC array and connected hosts will QE use, and when will approved access be available? | Open — Storage Working Group / partner workstream / QE | Determines readiness for automated FC acceptance. |
| OQ-3 | Which NetApp-specific retained-volume and partial-cleanup recovery procedure satisfies the shared offboarding contract, including cleanup timing and credential removal? | Open — Storage Working Group / Core-secrets workstream | Completes operational recovery guidance while preserving deletion guards; no NetApp-specific grace period is established. |

---

## Provenance

Authored: draft @ prd 0.11.3 - 2bd6607, workspace main @ c5819927b
Final: revise @ prd 0.11.3 - 2bd6607, workspace osac-5813-netapp-integration @ c5819927b

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"c5819927b","source_repo_branch":"osac-5813-netapp-integration","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
