# NICo backend for usable bare-metal instances

| Field | Value |
|---|---|
| Author(s) | Vladik Romanovsky |
| Jira | [OSAC-7195](https://redhat.atlassian.net/browse/OSAC-7195) |
| Date | 2026-11-05 |
| Target milestone | Initial NICo BMaaS increment; release version unassigned |

## Problem Statement

An OSAC tenant can request a BareMetalInstance (BMI), but the NICo hardware
pilot has only demonstrated allocation, address reporting, and eventual
cleanup. It reported the BMI as running while the tray had booted a discovery
environment rather than the operating system named in the request. Provider
administrators also had to configure tenant, network, pool, and credentials
manually for the pilot. Until the boot outcome, network access, tenant
boundaries, and cleanup behavior are reliable, tenants cannot use this path to
obtain a trusted, usable bare-metal machine.

## In Scope

- **BMaaS, initial NICo path:** A tenant can create, inspect, and delete one
  NICo-backed BMI through OSAC's existing API and CLI, using a published
  catalog offering. The tenant supplies an approved operating-system choice,
  an SSH public key, and at most one network attachment. OSAC reports the
  selected Machine, assigned IPv4 address, and meaningful provisioning or
  deletion progress.
- **Provider setup:** An administrator can make a NICo tenant, site, Ready
  Machine pool, supported ARM64 boot option, and pre-existing FNN network
  available to an OSAC tenant and BMI offering. Setup and redeployment are
  repeatable without editing generated runtime IDs. Tenant requests cannot
  name another tenant's NICo resources or supply provider credentials.
- **Usable boot:** The operating system shown in OSAC as the selected
  DiskImage must correspond to the OS actually installed on the chosen tray.
  Unsupported image choices are rejected before NICo allocation. A BMI is
  reported as running only after the selected OS has booted and the supplied
  SSH key permits access; allocation or iPXE handoff alone is insufficient.
- **FNN attachment:** For an administrator-prepared NICo FNN VPC and Prefix,
  the OSAC Subnet and requested IPv4 CIDR must match the approved network.
  The BMI reports its assigned address and can be reached from an authorized
  endpoint on that network. A missing, mismatched, or unready network is
  reported as a provisioning error without allocating a Machine. A request
  with SecurityGroup policy that this NICo path cannot honor is rejected
  before allocation rather than accepted without enforcement.
- **Ownership and cleanup:** NICo selects from the approved Ready pool.
  OSAC keeps the provider Instance and original Machine identifiable to
  administrators, including during retries. An uncertain create result must
  not allocate a second Instance. Deletion remains in progress until only
  the owned Instance has been removed and its original Machine is again
  unassigned and Ready; temporary NICo failures remain visible and retryable.
- **Credentials and validation:** Provider and tenant access to NICo can be
  configured and rotated without exposing secret values to tenant requests
  or losing the ability to delete existing BMIs. Documentation and automated
  tests cover setup, tenant isolation, boot and network evidence, retry and
  cleanup behavior. A real-hardware test records the end-to-end result and
  clearly identifies any checks that could not be verified.

This increment is accepted when the following scenarios pass on a supported
NICo FNN site:

- [ ] A tenant creates a BMI from the catalog without entering NICo IDs or
  credentials. NICo selects an eligible Ready Machine from the configured
  pool, and OSAC shows its identity and assigned IPv4 address.
- [ ] The approved ARM64 OS represented by the selected OSAC DiskImage is
  installed and boots. OSAC reports running only after host-level evidence,
  and the provided SSH key works from an authorized endpoint.
- [ ] The instance's assigned address is in the approved Prefix and is
  reachable from an authorized endpoint. A mismatched tenant, Subnet, image,
  pool binding, or unsupported SecurityGroup policy fails before creating a
  NICo Instance.
- [ ] When the tenant deletes the BMI, OSAC keeps deletion visible during
  NICo cleanup and eventually removes the BMI after the original Machine is
  unassigned, Ready, and free of blocking aggregate health alerts. A
  repeated or interrupted request does not delete an unrelated Instance.
- [ ] An administrator can repeat setup and rotate NICo credentials without
  disclosing credentials or manually repairing numeric job-system IDs;
  existing BMIs remain deletable.

## Out of Scope

- NICo Day-0 hardware onboarding and Machine ingestion.
- OSAC creation or deletion of NICo VPCs, Prefixes, or network security
  groups. [OSAC-7351](https://redhat.atlassian.net/browse/OSAC-7351)
  covers the separate NICo FNN fabric-manager increment.
- NICo enforcement of OSAC SecurityGroup rules, ExternalIP, NAT, Flat/ETV
  networking, and IPv6.
- Direct HostedCluster worker enrollment, CaaS integration, and arbitrary
  OSAC containerDisk-to-NICo image conversion.
- A new tenant-facing console workflow; this increment uses the existing
  OSAC API and CLI.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to authorize a NICo-backed BMI catalog
  offering for a specific OSAC tenant and NICo tenant, so that tenant requests
  cannot consume another organization's hardware or credentials.
- As a Cloud Provider Admin, I want to see which NICo Instance and Machine
  belong to a BMI during provisioning and cleanup, so that I can investigate
  stuck allocations without risking another tenant's Instance.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to prepare an approved Ready Machine
  pool, ARM64 boot option, and FNN network for the BMI offering, so that
  tenants can obtain a usable machine without choosing provider resource IDs.
- As a Cloud Infrastructure Admin, I want repeatable setup and credential
  rotation instructions, so that the NICo backend remains operable across
  redeployments and existing machines can still be cleaned up.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to order a NICo-backed BMI with an
  approved operating system, my SSH public key, and a Subnet, so that I can
  log in to the selected bare-metal machine on the assigned IPv4 address.
- As a Tenant Admin or Tenant User, I want OSAC to distinguish boot progress,
  a usable running machine, provisioning failures, and deletion progress, so
  that I can tell when the machine is available and when it has been released.
- As a Tenant Admin or Tenant User, I want to delete my BMI through OSAC, so
  that its NICo allocation is released without manual provider intervention.

## Dependencies

- **NICo site readiness:** The provider must supply NICo-ingested Ready
  Machines in an eligible Instance Type or pool, tenant allocation, a
  supported ARM64 boot source, and a prepared FNN VPC and Prefix before this
  offering is enabled.
- **Reachability test path:** The provider must supply an authorized endpoint
  with a route to the prepared FNN Prefix to verify SSH and packet
  reachability. This feature verifies attachment to that network; it does not
  create the VPC or Prefix.
- **OSAC networking contract:** The BMI attachment must respect the existing
  connected IPv4, one-attachment Subnet model in the accepted
  [unified networking](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1433-unified-networking/design.md)
  and [BMaaS networking](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1437-bmaas-networking/design.md)
  designs. NICo-managed OSAC network lifecycle is planned separately in
  [OSAC-7351](https://redhat.atlassian.net/browse/OSAC-7351).

---

## Provenance

Authored: draft @ prd 0.8.0 - 7efcedb, workspace no-issue/nico-bmaas-integration-audit @ e71f63765

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"e71f63765","source_repo_branch":"no-issue/nico-bmaas-integration-audit","commits_behind_main":0,"commits_ahead_main":13,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
