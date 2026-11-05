# CSP-managed NetApp Storage for VMaaS

| Field | Value |
|---|---|
| Author(s) | Zoltan Szabo |
| Jira | [OSAC-5813](https://redhat.atlassian.net/browse/OSAC-5813) |
| Date | 2026-10-05 |
| Last updated | 2026-11-05 |
| Target milestone | OSAC 0.4 — Developer Preview |
| Status | Draft — aligned with delivered preview scope |

## Problem Statement

Providers can onboard tenants with OSAC-managed storage, but also need to offer
NetApp storage they operate themselves. The preview adds a shared, CSP-managed
NetApp offering for VMaaS, with visible onboarding results and tier selection
for VM disks.

## In Scope

- Register CSP-managed NetApp StorageBackends and FC block StorageTiers.
- Complete initial storage onboarding when every configured tier has exactly
  one matching, CSP-prepared StorageClass on the VMaaS target. Missing or
  duplicate classes and target access failures are visible to administrators;
  onboarding retries after correction.
- Use the shared VM workflow for boot and additional disks, checking the tiers
  requested by each VM. Tenant offboarding preserves CSP-owned shared storage.

The CSP prepares and qualifies the shared SVM, Trident, TridentBackendConfig and
StorageClasses, including FC access, credentials, certificate trust, performance,
encryption and authorized disk access. A shared SVM does not provide per-tenant
SVM isolation. The
[CSP preparation guide](https://github.com/osac-project/osac/blob/main/docs/storage/guides/csp-managed-netapp-shared.md)
describes these steps.
OSAC needs no NetApp management credentials and does not modify these resources.
Readiness verifies class availability, not array connectivity or working FC I/O;
initial success remains recorded while later VM requests check their own tiers.

## Out of Scope

- OSAC-managed NetApp, dedicated tenant SVMs, and automatic array or Trident setup.
- Standalone VaaS, dynamic attach/detach, CaaS/BMaaS and OSAC CSI integration.
- NFS, iSCSI and other non-FC transports for this preview.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to register my prepared NetApp tiers, so that
  tenants can select the storage offerings I operate.
- As a Cloud Provider Admin, I want onboarding failures to identify missing or
  ambiguous classes and target access problems, so that I can correct the setup.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want a preparation guide for the shared
  storage resources and their ownership, so that I can configure and support
  the offering without OSAC changing my infrastructure.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to select a NetApp tier for each VM
  disk, so that my workloads use the offered persistent storage without array
  management access.

## Dependencies

- [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037) owns the shared
  VM/Volume provisioning and cleanup workflow; this feature supplies tier readiness.

---

## Provenance

Authored: draft @ prd 0.11.3 - 2bd6607, workspace main @ c5819927b
Final: revise @ prd 0.11.5 - 70405a6, workspace OSAC-6685-storage-handoff-go-fixture @ c8f8f513d

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"70405a6","source_repo":"c8f8f513d","source_repo_branch":"OSAC-6685-storage-handoff-go-fixture","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","revise","revise","revise","respond","revise","revise","revise","revise","revise","revise","revise","revise","revise","respond","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
