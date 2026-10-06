# Tenant Onboarding for NetApp ONTAP Storage

| Field | Value |
|---|---|
| Author(s) | Zoltan Szabo |
| Jira | [OSAC-5813](https://redhat.atlassian.net/browse/OSAC-5813) |
| Date | 2026-10-05 |
| Last updated | 2026-10-06 |
| Target milestone | OSAC 0.4 — Developer Preview (VMaaS; VaaS stretch goal) |

## Problem Statement

Cloud Provider Admins already onboard tenants to VAST-backed storage through
OSAC, but NetApp ONTAP over Fibre Channel (FC) lacks an automated integration.
The Developer Preview needs a complete VM provisioning journey with isolated
NetApp-backed disks on one existing OpenShift cluster, without installing or
requiring the OSAC CSI driver. Tenants need ready, persistent disks and accurate
provisioning/deletion status throughout the normal VM lifecycle.

## In Scope

- Register one ONTAP backend and one or more FC block tiers through the existing
  UI, CLI, and API.
- Automatically onboard tenants into isolated SVMs with centrally managed
  credentials and usable configuration for their assigned tiers.
- Provision and consume NetApp-backed VM boot/additional disks through the normal
  OSAC VM workflow, with ownership, readiness, persistence and failure cleanup.
  The supported single-cluster deployment does not install or depend on the OSAC CSI driver.

Installation and infrastructure preparation may use documented CLI steps.
Attachment and offboarding retain the established safeguards from
[OSAC-23](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-23-tenant-storage-onboarding/prd.md),
[OSAC-2117](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-2117-pure-storage-flashblade/prd.md)
and [OSAC-4884](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-4884-volume-api-storage-attach-detach/prd.md).
Tenants receive no ONTAP management credentials.

**Stretch goal:** independently managed VaaS volumes and dynamic attach/detach.

### Required verification

Onboard two tenants and create VMs through the UI and API/CLI using NetApp tiers.
Failed onboarding remains not ready. Verify FC I/O, tenant isolation, persistence across stop/start, deletion cleanup,
accurate provisioning/deletion failures, and safe retries after control-plane
restart. Confirm the OSAC CSI driver is absent. Acceptance may be executed
manually; per-VM manual disk provisioning does not replace the supported workflow.

## Out of Scope

- CaaS and BMaaS storage integration, Enclave, and OSAC CSI driver deployment/integration.
- Multi-cluster or multi-backend preview deployment profiles.
- FC switch configuration, zoning, host/HBA preparation, and dedicated fabric diagnostics.
- NFS, iSCSI, FCoE, and NVMe/TCP transports.
- Migration between NetApp and other providers; supported in-place OSAC upgrades.
- Performance benchmarking or custom QoS beyond native provider capabilities.
- New NetApp-specific credential rotation or expiry-renewal automation.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want backend registration to report management
  connectivity or credential-validation failures, so that I can correct access
  before tenant onboarding.
- As a Cloud Provider Admin, I want multiple NetApp block tiers with native
  performance policies on the registered backend, so that tenants can select
  my storage offerings.
- As a Cloud Provider Admin, I want automatic isolated SVM onboarding with
  actionable privilege/resource-limit failures and safe retries, so that I can
  enable tenant storage without duplicate allocations.
- As a Cloud Provider Admin, I want provisioning and deletion failures to show
  safe, useful reasons through existing status views, so that I can recover
  partial resources while preserving tenant data and lifecycle safeguards.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to select an assigned NetApp tier for
  VM boot and additional disks through the existing UI, API, and CLI, so that
  my VM receives usable disks without separate manual disk provisioning.
- As a Tenant Admin or Tenant User, I want VM disk data to persist across stop/start
  and deletion behavior to be documented, so that I understand my data lifecycle.
- **Stretch goal:** As a Tenant Admin or Tenant User, I want independently managed
  NetApp volumes and authorized VM attach/detach, so that volume lifecycle can be
  independent of compute.

## Assumptions

- One existing, connected OpenShift cluster with OpenShift Virtualization hosts
  OSAC and tenant VMs; no separate hub or workload cluster is required.
- Infrastructure administrators supply workers with supported FC access, prepared
  zoning, management connectivity, sufficient ONTAP privileges, and the required
  vendor storage deployment. These prerequisites use documented setup steps.
- Management access or SVM creation does not prove FC connectivity; infrastructure
  owners complete any zoning needed for newly created tenant targets.
- Existing central credential handling and lifecycle safeguards apply.

## Dependencies

- Existing Core/secrets support and configuration/onboarding handoffs.
- A supported NetApp volume-to-VM integration, including the shared VM/Volume
  lifecycle work in [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037),
  that delivers disks to the VM workflow without the OSAC CSI driver.
- An FC-capable array and connected OpenShift workers for acceptance. Relevant
  findings from [OSAC-5807](https://redhat.atlassian.net/browse/OSAC-5807) inform
  FC validation; OSAC CSI-specific investigation is not a preview prerequisite.
- OSAC-4884 supplies independent-volume attachment if the stretch goal is pursued;
  it is not required for the baseline VM disk lifecycle.

## Risks

- Management-only array access or workers without FC connectivity cannot establish
  VM consumption acceptance (OQ-2).
- An incomplete volume-to-VM handoff can leave registration/onboarding functional
  while VM provisioning, readiness or cleanup fails (OQ-1/OQ-3).

## Open Questions

| ID | Question | Status / owner | Impact |
|---|---|---|---|
| OQ-1 | Which supported NetApp path integrates VM disks with OSAC's volume lifecycle without the OSAC CSI driver? | Open — Storage Working Group / Feature owner | Defines the required volume-to-VM handoff; native Trident is a design option, not a confirmed choice. |
| OQ-2 | Which FC array and FC-connected OpenShift workers are available, and when is approved access ready? | Open — Storage Working Group / partner workstream / QE | Determines readiness for the required VM acceptance journey. |
| OQ-3 | Which partial-provisioning, retained-volume and failed-deletion recovery steps satisfy the shared lifecycle safeguards? | Open — Storage Working Group / Core-secrets workstream | Defines cleanup ownership and operational recovery without data loss or duplicate allocation. |

---

## Provenance

Authored: draft @ prd 0.11.3 - 2bd6607, workspace main @ c5819927b
Final: revise @ prd 0.11.3 - 2bd6607, workspace osac-5813-netapp-integration @ c8d0d8890

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"c8d0d8890","source_repo_branch":"osac-5813-netapp-integration","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","respond","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
