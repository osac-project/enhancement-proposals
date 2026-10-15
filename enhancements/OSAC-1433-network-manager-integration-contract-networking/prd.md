---
title: network-manager-integration-contract
authors:
  - dmanor@redhat.com
creation-date: 2026-10-04
last-updated: 2026-10-13
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1433
see-also:
  - Unified Networking PRD: /enhancements/OSAC-1433-unified-networking/prd.md
  - Unified Networking Design: /enhancements/OSAC-1433-unified-networking/design.md
  - Network Manager Integration Contract Design: /enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md
replaces:
  - N/A
superseded-by:
  - N/A
---

# Network Manager Integration Contract

| Field | Value |
|-------|-------|
| Author(s) | Dan Manor (dmanor@redhat.com) |
| Jira | https://redhat.atlassian.net/browse/OSAC-1433 |
| Date | 2026-10-08 |

## Contents

- [1. Problem Statement](#1-problem-statement)
- [2. Goals and Non-Goals](#2-goals-and-non-goals)
- [User Stories](#user-stories)
- [3. Requirements](#3-requirements)
  - [3.1 Functional Requirements](#31-functional-requirements)
  - [3.2 Non-Functional Requirements](#32-non-functional-requirements)
- [4. Dependencies](#4-dependencies)

## 1. Problem Statement

OSAC networking uses provider-selected Fabric and Kubernetes (K8s) managers, but providers do not have one clear way to tell which combinations work together or whether a new implementation meets OSAC's requirements. An incompatible combination can prevent workloads from joining the intended network. Providers and implementation authors must infer the integration expectations, making source-neutral onboarding and consistent networking across virtual machines (VMs), managed Kubernetes clusters, and bare-metal workloads difficult to assess. [User]

## 2. Goals and Non-Goals

### 2.1 Goals

- Cloud Infrastructure Admins can determine whether selected Fabric and K8s manager implementations can meet each other's networking needs before provider work starts.
- Providers can assess whether a manager implementation meets OSAC's complete role requirements using one published contract.
- Cloud Infrastructure Admins can provide the backend settings and credentials required by the provider-selected networking implementations.
- Providers can add shared network data definitions needed by new manager implementations without requesting manager-specific OSAC code.
- Tenants can use the same networking resources and workflows across compatible manager combinations for every workload service that integrates the shared model.
- Providers can select an implementation regardless of who supplies it, without changing tenant networking workflows.
- Cloud Infrastructure Admins receive a clear rejection before dependent work starts when a data definition is invalid, a manager pair cannot exchange a required value, or a produced value does not meet its registered definition.

### 2.2 Non-Goals

- Changing the shared tenant networking resources or their meaning.
- Requiring every Fabric Manager to work with every K8s Manager.
- Exposing provider manager selection to tenants.
- Defining a standard vendor-specific field set for Netris, Agentless VLAN, CUDN, or another backend.
- Proving from a data definition alone that a manager configured its backend correctly or preserved the shared networking behavior.
- Adding new OSAC resource kinds or manager operations solely by registering a data definition.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want one contract that states each manager role's requirements and which implementations can interoperate, so that I can select a supported provider configuration with clear diagnostics when a pairing or operation is unsupported.
- As a Cloud Infrastructure Admin, I want to create, inspect, and remove shared network data definitions and manager registrations through OSAC's provider management interface, so that OSAC can validate configuration before networking work uses it.
- As a Cloud Infrastructure Admin, I want OSAC to validate manager declarations and produced values against registered definitions, so that a new backend integration does not require manager-specific OSAC development.
- As a Cloud Infrastructure Admin, I want to configure backend settings and credentials for networking fulfillment, so that provider-selected manager implementations can reach their backend services.
- As a Cloud Infrastructure Admin, I want to distinguish manager registration from behavior qualification, so that a successful task response is not mistaken for evidence that connectivity, allocation, policy, and cleanup work.
- As a Cloud Infrastructure Admin, I want actionable blockers when manager work is interrupted or uncertain, so that OSAC does not declare dependent work ready, release addresses, or accept replacement managers prematurely.
- As a Cloud Infrastructure Admin, I want a published qualification to retain pass, fail, or incomplete results for my selected manager configuration, so that I can review its evidence before production use.

### Tenant User

- As a Tenant User, I want to use the shared networking resources across supported manager combinations, so that changing provider implementations does not change my networking workflow.

## 3. Requirements

### 3.1 Functional Requirements

- **FR-1:** A provider can select a conforming Fabric Manager or K8s Manager implementation regardless of who supplies it; OSAC-provided implementations meet the same requirements. [User]
- **FR-2:** A Cloud Infrastructure Admin must be able to determine from one published contract what each manager role requires and whether selected implementations can meet those requirements. [User]
- **FR-3:** Tenants can use the same OSAC networking resources and workflows across compatible manager combinations for every workload service that integrates the shared model, without selecting a provider backend. [Unified Networking PRD: FR-2, FR-6] [User]
- **FR-4:** When selected implementations cannot meet a required networking dependency, a required role is unavailable, or a request is outside the supported manager contract, the Cloud Infrastructure Admin must receive a clear diagnostic and OSAC must reject the request rather than route it through an unrelated manager. [User]
- **FR-5:** A provider can define additional shared networking data for existing provider profiles, VirtualNetworks, and Subnets, then exchange it between conforming managers without one-off OSAC changes or a tenant API change. Concurrent operations that produce the same shared value converge on one consistent value and backend allocation. [User]
- **FR-6:** OSAC must identify invalid data definitions, undefined manager references, missing required data, and values that do not match their definition, and prevent dependent work from starting. [User]
- **FR-7:** Cloud Infrastructure Admins can create, inspect, list, and remove manager and data-model registrations through OSAC's provider management interface; OSAC rejects attempts to modify an existing registration in place. [User]
- **FR-8:** Cloud Infrastructure Admins can provide backend settings and credentials required by the provider-selected networking managers, so manager jobs can reach their backend services. [User]

- **FR-9:** A Cloud Infrastructure Admin can distinguish manager registration and successful task handling from provider behavior qualification; a successful manager result alone does not prove that advertised connectivity, address allocation, policy, or cleanup occurred. [User]
- **FR-10:** When manager work is interrupted or its outcome is uncertain, OSAC does not report dependent resources as ready, release address capacity, or permit replacing the bound manager/profile until the relevant work is resolved. OSAC gives the Cloud Infrastructure Admin an actionable blocker. [User]
- **FR-11:** A Cloud Infrastructure Admin can run the published networking qualification against the provider's selected manager configuration and receive a retained pass, fail, or incomplete report for required operations, targets, capabilities, recovery, and cleanup. A skipped required assertion is incomplete, not a pass. [User]
- **FR-12:** Every supported workload attachment receives its tenant IPv4 address and standard network settings through Dynamic Host Configuration Protocol (DHCP). The provider qualifies this behavior for the selected manager combination; valid registrations or successful task results alone do not prove it. [Unified Networking PRD: FR-1] [User]

### 3.2 Non-Functional Requirements

No separate non-functional requirements were specified for this work.

## 4. Dependencies

- **Unified Networking:** Its PRD and design define the shared networking resources, provider manager roles, and tenant-visible behavior that conforming implementations must preserve.
- **Provider manager implementations:** Fabric and K8s managers selected by a provider must meet the published requirements and make clear which networking information they can provide and which information they need, so OSAC can identify configurations that can work together.
- **Provider-defined data definitions:** Providers describe the meaning, owning networking resource, and valid shape of each shared value. Manager implementations must preserve that meaning and the shared networking behavior; data validation alone cannot prove backend behavior.

---

## Provenance

Authored: draft @ prd 0.11.3 - 2bd6607, workspace main @ 1f3b63b82 (52 behind origin/main)
Final: revise @ prd 0.11.5 - 1c6e8de, workspace main @ 97d046f86 (16 behind origin/main)

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"97d046f86","source_repo_branch":"main","commits_behind_main":16,"commits_ahead_main":0,"main_ref":"main","phases":["draft","manual-edit","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","manual-edit","manual-edit","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":false} -->
