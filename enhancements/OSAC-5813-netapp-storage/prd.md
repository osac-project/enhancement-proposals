# Tenant Onboarding and Offboarding for NetApp ONTAP Storage

| Field | Value |
|---|---|
| Author(s) | Zoltan Szabo |
| Jira | [OSAC-5813](https://redhat.atlassian.net/browse/OSAC-5813) |
| Date | 2026-10-05 |
| Last updated | 2026-10-12 |
| Target milestone | OSAC 0.4 — Developer Preview (VMaaS integration) |
| Status | Draft — prepared-SVM adoption; team agreement pending |

## Problem Statement

Cloud Provider Admins already onboard tenants to VAST-backed storage through
OSAC, but lack equivalent tenant onboarding/offboarding for NetApp ONTAP
over Fibre Channel (FC). Providers need isolated tenant storage configuration
and clear lifecycle status so that the shared VMaaS workflow can consume their
NetApp tiers in the Developer Preview.

## In Scope

- Register one ONTAP backend and one or more FC block tiers through the existing
  UI, CLI, and API.
- Bind each tenant to its dedicated, administrator-prepared storage virtual
  machine (SVM), with protected management access and usable configuration for
  its assigned tiers. The management-endpoint model remains open (OQ-5).
- Offboard tenant storage using the established lifecycle safeguards.

Administrators prepare dedicated SVMs with usable capacity, LIFs, trusted
management access, provisioning credentials, matching native policies and a
qualified vendor-driver deployment using documented manual steps before OSAC adoption.
Offboarding follows
[OSAC-23](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-23-tenant-storage-onboarding/prd.md),
[OSAC-2117](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-2117-pure-storage-flashblade/prd.md)
and their data/dependency guards; completion confirms removal of OSAC-owned
configuration and the departing tenant's OSAC access. Administrator-prepared
SVMs, LIFs, accounts and credential sources are retained; reuse requires verified
data/access cleanup and explicit administrator authorization.
Tenants receive no ONTAP management credentials.

### Required verification

Onboard two tenants and verify distinct SVMs, the agreed management-access model
and correct tier bindings. Each tenant VM can use only its own assigned disks,
including when VMs of different tenants share a worker (OQ-6). FC requires no separate
tenant IP data LIF; its target LIFs and access configuration follow ONTAP's FC
model. Failed onboarding remains not ready and retries avoid duplicate resources.
Offboarding respects data/dependency guards, removes OSAC-owned resources/access,
preserves prepared infrastructure and the other tenant's storage, and rejects
unsafe reassignment. QE validates the resulting configuration
through the shared VMaaS-over-FC flow; VM disk lifecycle implementation is a
separate dependency below. Setup and acceptance may be performed manually.
Acceptance covers VM hosting on the hub and on a dedicated remote cluster,
with one hosting target configured per deployment.

## Out of Scope

- Shared VM/Volume lifecycle implementation, independent VaaS volumes and dynamic attach/detach.
- OSAC CSI integration changes or removal, and vendor-driver installation automation.
- CaaS and BMaaS storage integration, and Enclave.
- Concurrent VM hosting targets or multiple storage backends per deployment.
- FC switch configuration, zoning, host/HBA preparation, and dedicated fabric diagnostics.
- NFS, iSCSI, FCoE, and NVMe/TCP transports.
- Migration between NetApp and other providers; supported in-place OSAC upgrades.
- Performance benchmarking or custom QoS beyond native provider capabilities.
- New NetApp-specific credential rotation or expiry-renewal automation.
- Automatic SVM/LIF creation/deletion, allocation from a free SVM pool, and
  automatic sanitization or recycling.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want backend registration to report management
  connectivity or credential-validation failures, so that I can correct access
  before tenant onboarding.
- As a Cloud Provider Admin, I want multiple NetApp block tiers with native
  performance policies on the registered backend, so that tenants can select
  my storage offerings.
- As a Cloud Provider Admin, I want OSAC to adopt each tenant's prepared SVM
  and report missing preparation or onboarding failures, so that I can correct
  the setup and retry safely.
- As a Cloud Provider Admin, I want tenant offboarding to report completion or
  safe, actionable failures under existing dependency guards, so that I can
  recover cleanup and prevent tenant state leaking into subsequent assignments.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want instructions for preparing each
  tenant's SVM and identifying what remains after offboarding, so that I can
  supply the storage prerequisites and manage retained resources.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want my assigned NetApp tiers to become
  available after onboarding, so that I can use the existing VMaaS workflow
  without handling ONTAP management credentials.

## Assumptions

- One existing, connected OpenShift Virtualization cluster hosts tenant VMs,
  either on the OSAC hub or as a dedicated remote hosting cluster. The preview
  profile operates without the OSAC CSI driver; existing CSI integrations remain intact.
- Infrastructure administrators supply workers with supported FC access, prepared
  zoning, reachable management endpoints with valid trusted certificates, and
  the required vendor storage deployment.
  These prerequisites use documented setup steps.
- Dedicated prepared-SVM adoption is the proposed preview model, pending team
  agreement on administrator prerequisites (OQ-4).
- Management access does not prove FC connectivity; infrastructure owners prepare
  tenant targets and zoning before onboarding.
- Existing central credential handling and lifecycle safeguards apply.
- Administrators provide an HTTPS management endpoint and protected provisioning
  credentials for each tenant's assigned SVM. This access is separate from FC
  disk traffic. A separate SVM management LIF (logical interface providing that
  SVM's management address) is the proposed preview profile; the supported
  endpoint/account scope remains subject to agreement (OQ-5).

## Dependencies

- Existing Core/secrets support and configuration/onboarding handoffs.
- [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037) owns the shared
  VM/Volume lifecycle, including disk creation, ownership and cleanup. This
  feature supplies tenant/tier storage configuration; the consumption handoff
  needs agreement with that workstream (OQ-1).
- QE and infrastructure owners provide an FC-capable ONTAP environment and
  connected workers for joint VMaaS acceptance (OQ-2).

## Risks

- Management-only array access or workers without FC connectivity cannot establish
  VM consumption acceptance (OQ-2).
- Incomplete prepared storage or credentials block onboarding (OQ-4); retained
  resources need verified data/access cleanup before reuse (OQ-3).
- A mismatch with the shared consumption configuration can block VM acceptance
  despite successful tenant resource creation (OQ-1).

## Open Questions

Owners track these items during implementation and close them with the evidence
below. Owning implementation/QE tasks will be linked when available.

| ID | Question | Status / owner | Closure evidence |
|---|---|---|---|
| OQ-1 | Which tenant/tier configuration does the shared VM consumption path require, and who owns any NetApp-specific adaptation? | Open — Configuration/onboarding developers / OSAC-6037 workstream | Agreed handoff and successful shared VM disk provisioning using the onboarding output. |
| OQ-2 | Has the intended NetApp environment demonstrated working FC consumption from its OpenShift workers? | Management discovery exercised; native provisioning/FC validation pending — QE / infrastructure owners | Recorded native VM disk provisioning and FC I/O on the target environment. |
| OQ-3 | Do the recovery, offboarding and manual-reuse safeguards preserve tenant isolation? | Verification pending — Onboarding developer / QE / infrastructure owners | Guarded retry/offboarding, retained-resource checks and rejection of reuse before verified cleanup and administrator authorization. |
| OQ-4 | Are dedicated administrator-prepared SVMs and their operational prerequisites accepted for the preview? | Proposed — Infrastructure owners / Feature owner | Accepted preparation checklist and available SVMs, usable capacity and protected onboarding inputs. |
| OQ-5 | Does the preview use separate SVM management endpoints or a shared endpoint, with which credential scope? | Open — Onboarding developer / infrastructure owners / reviewers | Agreed endpoint/account profile and successful native provisioning with it. |
| OQ-6 | Are tenant VMs sharing a worker limited to their own assigned disks? | Vendor initiator reuse is documented; integration validation pending — Onboarding/shared VM developers / QE | Two tenants provision and use their own disks on a shared worker; cross-tenant disk access is rejected. |

---

## Provenance

Authored: draft @ prd 0.11.3 - 2bd6607, workspace main @ c5819927b
Final: respond @ prd 0.11.5 - 1c6e8de, workspace OSAC-5813-netapp-backend-tiers @ 6a7787eb0

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"6a7787eb0","source_repo_branch":"OSAC-5813-netapp-backend-tiers","commits_behind_main":0,"commits_ahead_main":7,"main_ref":"main","phases":["draft","revise","revise","revise","respond","revise","revise","revise","revise","revise","revise","revise","revise","revise","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
