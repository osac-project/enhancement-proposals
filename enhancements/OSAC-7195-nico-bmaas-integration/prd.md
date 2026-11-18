# NICo Backend Integration for BMaaS

| Field | Value |
|-------|-------|
| Author(s) | Nick Carboni |
| Jira | [OSAC-7195](https://redhat.atlassian.net/browse/OSAC-7195) |
| PRD task | [OSAC-7894](https://redhat.atlassian.net/browse/OSAC-7894) |
| Date | 2026-11-18 |
| Target milestone | 0.6 |
| Related PRDs | [BCM](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1339-bcm-backend/prd.md), [NetBox](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1610-netbox-inventory/prd.md) |

## Problem Statement

Cloud Infrastructure Admins need to make NICo-managed bare-metal hosts available
through OSAC. OSAC provides a BareMetalInstance workflow with DiskImage and
BareMetalInstanceType selections, but does not yet support that workflow with
NICo. Tenants need to receive the selected operating system on
matching hardware, see whether provisioning succeeds, and release the host
through OSAC.

## In Scope

- Individual host provisioning, inspection, and deprovisioning through OSAC's
  standard BMaaS workflow, using an administrator-prepared NICo environment with
  OSAC networking provisioning disabled.
- Administrator setup of NICo access, eligible hardware, and mappings for OSAC
  DiskImages and BareMetalInstanceTypes, including OSAC installer configuration.
- Automated tests and end-to-end validation of the NICo-backed host lifecycle.
- Documentation for backend setup, image and hardware mappings, support limits,
  and recovery.

## Out of Scope

- NICo hardware onboarding and ingestion before OSAC can use the hosts.
- OSAC-managed NICo networking, fabric-manager integration, network lifecycle,
  and network-policy enforcement.
- Direct CaaS or HostedCluster worker integration.
- New tenant workflows in the OSAC web console.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to configure NICo as the backend so
  that OSAC can provision hosts from my existing NICo environment.
- As a Cloud Infrastructure Admin, I want to associate OSAC DiskImages and
  BareMetalInstanceTypes with their NICo equivalents so that requests provision
  the selected operating system on matching hardware.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to offer NICo-backed hosts through the
  existing OSAC catalog and access controls so that tenants can request approved
  hardware and images through the normal workflow.

### Tenant User

- As a Tenant User, I want to request an individual host using a DiskImage and
  BareMetalInstanceType so that I receive the selected operating system on
  matching hardware.
- As a Tenant User, I want to see provisioning progress and success or failure
  so that I know the outcome of my request.
- As a Tenant User, I want to deprovision my host through OSAC so that it is
  released for reuse.

## Assumptions

- An administrator prepares the NICo hardware, boot prerequisites, and required
  site connectivity before OSAC provisions hosts.

## Dependencies

- An existing NICo environment with the access and provider capabilities needed
  to provision the selected OS on matching hardware and release the host.
- OSAC's existing BareMetalInstance workflow, DiskImages,
  BareMetalInstanceTypes, catalog, and access controls.

---

## Provenance

Authored: revise @ prd 0.11.5 - 7653641, workspace main @ fb227b4fd
Phases: draft, revise, revise, revise, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7653641","source_repo":"fb227b4fd","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
