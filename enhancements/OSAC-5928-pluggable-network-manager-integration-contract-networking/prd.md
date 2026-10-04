---
title: Network Manager Integration Contract
authors:
  - dmanor@redhat.com
creation-date: 2026-10-04
last-updated: 2026-10-04
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-5928
see-also:
  - Unified Networking PRD: /enhancements/OSAC-1433-unified-networking/prd.md
  - Unified Networking Design: /enhancements/OSAC-1433-unified-networking/design.md
  - Network Manager Integration Contract Design: /enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md
replaces:
  - N/A
superseded-by:
  - N/A
---

# Network Manager Integration Contract

| Field       | Value |
|-------------|-------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-5928 |
| Date        | 2026-10-04 |

## 1. Problem Statement

OSAC networking designs describe manager roles and provisioning, but the manager obligations are mixed into the Unified Networking architecture and implementation examples. Implementers must infer what a Fabric Manager or K8s Manager needs to provide, making it unclear whether an implementation for a different networking stack will work with OSAC. Providers need one source-neutral contract that states the requirements for every implementation, including those distributed with OSAC. [User]

## 2. Goals and Non-Goals

### 2.1 Goals

- A Cloud Infrastructure Admin can select a conforming Fabric Manager or K8s Manager implementation regardless of who supplies it.
- An implementation author can determine the full conformance requirements from one normative contract.
- Tenants continue using the same OSAC networking API when a provider selects a different conforming implementation.
- A selected networking profile routes each operation to its assigned manager role; when the profile cannot route a request, OSAC gives a clear diagnostic and does not send it to a different role. [User]

### 2.2 Non-Goals

- Changing tenant-facing networking resources or their semantics.
- Defining backend-specific resource mappings for Netris, Agentless VLAN, or other networking products.
- Letting implementations add resource kinds or operations that OSAC does not recognize.

## 3. Requirements

### 3.1 Functional Requirements

- **FR-1:** An implementation author must be able to use one published OSAC contract to integrate a Fabric Manager or K8s Manager, regardless of who supplies the implementation. Implementations distributed with OSAC use the same contract. [User]
- **FR-2:** An implementation author must be able to determine from the contract the manager role responsibilities, every required operation and workload target, registration requirements, task inputs and results, lifecycle behavior, and failure handling. A conforming implementation must provide the complete operation set assigned to its role. [User]
- **FR-3:** A Cloud Infrastructure Admin must be able to configure conforming implementations for the manager roles while tenants continue using the shared OSAC networking API. [Unified Networking PRD: FR-6]
- **FR-4:** When the selected profile does not route a requested operation and workload target, or lacks the manager role required by the fixed dispatch rules, OSAC must give the provider a clear diagnostic and must not route that work to a different manager. [User]

## 4. Acceptance Criteria

- [ ] The published contract defines the exact v1 registration, role, complete operation and target sets, input, output, lifecycle, error, and security requirements for Fabric and K8s Manager implementations.
- [ ] An implementation from any source, including an implementation distributed with OSAC, is eligible for selection when it conforms to the published contract.
- [ ] A provider can select conforming manager implementations without changing the tenant-facing OSAC networking API.
- [ ] Invalid registrations and operation-target pairs unavailable in the selected profile produce a clear diagnostic before OSAC dispatches work; a registration cannot opt out of required operations.
- [ ] The Unified Networking design explains OSAC profile selection and orchestration and links to the standalone contract for exact implementation requirements.
- [ ] Netris and Agentless VLAN designs reference the same contract as their implementation interface.

## 5. Dependencies

- **Unified Networking API and dispatch:** The contract applies to the Fabric Manager and K8s Manager roles and operation routing defined by Unified Networking.
- **AAP execution environment:** The selected implementation's Ansible collection role must be available to the deployed execution environment.

---

## Provenance

Authored: revise @ prd 0.11.3 - 2bd6607, workspace main @ 1f3b63b82 (52 behind origin/main)
Phases: draft, manual-edit, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"1f3b63b82","source_repo_branch":"main","commits_behind_main":52,"commits_ahead_main":0,"main_ref":"main","phases":["draft","manual-edit","revise"],"authoring_modes":["manual","skill"],"context_changed":false,"origin_untracked":false} -->
