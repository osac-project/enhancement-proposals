# Tenant Onboarding and Offboarding for NetApp ONTAP Storage

| Field | Value |
|---|---|
| Author(s) | Zoltan Szabo |
| Jira | [OSAC-5813](https://redhat.atlassian.net/browse/OSAC-5813) |
| Date | 2026-10-05 |
| Last updated | 2026-10-16 |
| Target milestone | OSAC 0.4 — Developer Preview (VMaaS integration) |
| Status | Draft — shared administrator-managed Trident backend |

## Problem Statement

Cloud Provider Admins already onboard tenants to VAST-backed storage through
OSAC, but lack equivalent NetApp ONTAP integration over Fibre Channel (FC).
Providers need to expose their prepared NetApp offerings to tenants and see
whether onboarding succeeded, so the shared VMaaS workflow can use those offerings.

## In Scope

- Register ONTAP backends and FC block tiers referencing administrator-prepared
  shared Trident backends and storage pools.
- Onboard tenants with their own tier bindings and visible storage readiness.
- Offboard OSAC-owned tenant storage configuration using the established
  lifecycle safeguards while retaining shared customer infrastructure.

Administrators prepare the array, FC access, Trident backend, credentials,
server certificate trust, native performance policies and encryption settings.
OSAC uses this preparation; it does not configure the array. Offboarding follows
[OSAC-23](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-23-tenant-storage-onboarding/prd.md)
and [OSAC-2117](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-2117-pure-storage-flashblade/prd.md)
and their data/dependency guards. Tenant management credentials are not exposed
to Tenant Admins or Tenant Users.

### Required verification

Two tenants receive the intended tiers through the shared backend. Failed setup
stays not ready; retries avoid duplicate configuration. Offboarding removes only
the departing tenant's OSAC-owned configuration and preserves shared resources
and the other tenant's storage. QE verifies FC VM disk persistence and authorized
disk access, including tenant VMs sharing a worker. Shared storage does not imply
per-tenant SVM isolation. Administrators qualify the prepared pools' performance
and encryption outcomes. Setup and acceptance may use documented manual steps.
The hosting target is the hub or one configured dedicated VM cluster.

## Out of Scope

- Per-tenant SVM/TBC provisioning, dedicated storage mode, free-SVM allocation,
  automatic sanitization and native credential-rotation automation.
- Shared VM/Volume lifecycle implementation, independent VaaS and dynamic attach/detach.
- OSAC CSI integration changes/removal, vendor-driver installation automation,
  CaaS/BMaaS storage and Enclave.
- Multiple concurrent hosting targets or multiple storage backends per deployment.
- FC switch/zoning/HBA configuration; NFS, iSCSI, FCoE and NVMe/TCP transports.
- Provider migration, supported in-place upgrades and performance benchmarking.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to register prepared NetApp storage offerings,
  so that tenants can select my FC block tiers.
- As a Cloud Provider Admin, I want missing or unusable prepared storage to appear
  as onboarding failures, so that I can correct the setup and retry.
- As a Cloud Provider Admin, I want offboarding to report completion or actionable
  cleanup failures, so that I can recover without disrupting shared storage.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want a preparation guide identifying the
  shared Trident backend, pool policies, trust and retained resources, so that I
  can provide the prerequisites and diagnose native connection failures.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want my assigned NetApp tiers to become
  available after onboarding, so that I can use the existing VMaaS workflow
  without handling ONTAP management credentials.

## Assumptions

- One existing connected OpenShift Virtualization hosting cluster has qualified
  Trident and FC-connected workers; the preview operates without the OSAC CSI driver.
- The administrator-managed shared pools provide the advertised performance and
  encryption. Shared-host disk access is qualified through the platform boundary;
  tier/class separation alone does not establish tenant isolation.

## Dependencies

- Matching registration/operator/AAP interfaces and documented manual preparation.
  Initial delivery can use CLI/API; UI support is owned by the UI team.
- [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037) supplies shared VM/Volume
  identity, provisioning and cleanup; this feature supplies ready tier bindings.
- QE/infrastructure owners provide an authorized FC-capable environment for joint
  VM acceptance. Registration acceptance does not establish array connectivity.

## Risks

- A usable catalog entry or bound Trident backend does not prove FC I/O.
- Wrong pool selection or unsafe cleanup can affect shared infrastructure; exact
  backend/pool selection, ownership guards and joint acceptance are required.

## Open Questions

| ID | Question | Owner / closure evidence |
|---|---|---|
| OQ-1 | Does the shared VM path consume the published tenant/tier bindings correctly? | Onboarding / OSAC-6037 owners; successful VM disk provisioning and lifecycle. |
| OQ-2 | Does the intended environment demonstrate encrypted FC VM disk use? | Infrastructure / QE; recorded native provisioning, encryption outcome and I/O. |
| OQ-3 | Does guarded cleanup preserve shared resources and other tenants? | Onboarding / QE; failed/retried cleanup and retained-resource checks. |
| OQ-6 | Can tenant VMs on a shared worker access only their authorized disks? | Shared VM / infrastructure / QE; cross-tenant selection and guest-access tests. |

---

## Provenance

Authored: draft @ prd 0.11.3 - 2bd6607, workspace main @ c5819927b
Final: revise @ prd 0.11.5 - 0c7ea35, workspace OSAC-5813-netapp-backend-tiers @ f629804cd

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"0c7ea35","source_repo":"f629804cd","source_repo_branch":"OSAC-5813-netapp-backend-tiers","commits_behind_main":0,"commits_ahead_main":17,"main_ref":"main","phases":["draft","revise","revise","revise","respond","revise","revise","revise","revise","revise","revise","revise","revise","revise","respond","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
