---
title: network-manager-integration-contract
authors:
  - dmanor@redhat.com
creation-date: 2026-10-04
last-updated: 2026-10-22
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
| Date | 2026-10-22 |

## Contents

- [1. Problem Statement](#1-problem-statement)
- [2. Goals and Non-Goals](#2-goals-and-non-goals)
  - [2.1 Goals](#21-goals)
  - [2.2 Non-Goals](#22-non-goals)
- [3. User Stories](#3-user-stories)
  - [3.1 Cloud Infrastructure Admin](#31-cloud-infrastructure-admin)
  - [3.2 Tenant User](#32-tenant-user)
- [4. Requirements](#4-requirements)
  - [4.1 Functional Requirements](#41-functional-requirements)
  - [4.2 Non-Functional Requirements](#42-non-functional-requirements)
- [5. Dependencies](#5-dependencies)

## 1. Problem Statement

Providers need a written statement of what the Fabric Manager must do and how OSAC uses it, and tests that prove it works; otherwise they guess task duties and order, and mistake a successful task for working connectivity, addressing, isolation, or cleanup.

## 2. Goals and Non-Goals

### 2.1 Goals

- Providers plug in their fabric by writing only a Fabric Manager to one published contract (FR-1, FR-2, FR-7, FR-8).
- A conforming Fabric Manager works with every workload service and with each OSAC Kubernetes Manager whose network type it declares (FR-3, FR-5).
- Providers prove their Fabric Manager with a repeatable conformance suite (FR-9, FR-11).

### 2.2 Non-Goals

- Provider-written Kubernetes Managers.
- Network types other than `evpn` in this release.
- Deployments outside the Unified Networking [support boundaries](/enhancements/OSAC-1433-unified-networking/design.md#networking-hub-support-boundary).
- More than one network attachment per workload.

## 3. User Stories

### 3.1 Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want one published contract for the Fabric Manager, so that I can implement or select one without guessing its tasks, inputs, outputs, or lifecycle.
- As a Cloud Infrastructure Admin, I want to register the Fabric Manager and select managers in NetworkClass, so that OSAC runs networking work through the contract.
- As a Cloud Infrastructure Admin, I want to give the managers their backend settings and credentials, so that they can reach their backends.
- As a Cloud Infrastructure Admin, I want to run the published conformance suite and know what it verifies (SecurityGroups: one VM check; full enforcement on each manager is a follow-up), so that I can tell registration apart from working connectivity, allocation, policy, and cleanup.

### 3.2 Tenant User

- As a Tenant User, I want the same networking resources whatever manager implementation the provider uses, so that a change of implementation does not change my workflow.

## 4. Requirements

### 4.1 Functional Requirements

- **FR-1:** Every Fabric Manager, whoever supplies it, follows one contract, and any conforming one works with each OSAC-shipped Kubernetes Manager whose network type it declares.
- **FR-2:** A Fabric Manager author can learn from one published contract what the Fabric Manager must do and how OSAC uses it, with no provider-specific OSAC code.
- **FR-3:** Tenants use the same OSAC networking resources across workload services without selecting a provider backend. [Unified Networking PRD: FR-2, FR-6]
- **FR-4:** An unknown manager name, a manager of the wrong type, an unknown capability or network type, a Kubernetes Manager not shipped by OSAC, a Kubernetes Manager whose network type the Fabric Manager does not declare, or a task outside the manager type's task set fails with a clear diagnostic; OSAC never substitutes another manager.
- **FR-5:** For a Subnet with a Kubernetes Manager, the Fabric Manager returns the Subnet's network segment for the network type (for `evpn`, its VNIs). OSAC validates it, stores it once on the Subnet, and passes it to the Kubernetes Manager; managers never exchange values directly.
- **FR-6:** OSAC accepts results only from the job it launched and rejects a malformed typed output (such as `vm_attachment`) with an actionable diagnostic before dependent work starts.
- **FR-7:** Cloud Infrastructure Admins register the Fabric Manager with a registration ConfigMap (OSAC registers its own Kubernetes Managers), select managers for a deployment, and get a clear diagnostic when a selected implementation cannot be used.
- **FR-8:** Cloud Infrastructure Admins can give the selected managers their backend settings and credentials, which never appear in tenant-facing networking resources.
- **FR-9:** A Cloud Infrastructure Admin can tell registration and task success apart from behavioral conformance: the tests check the Fabric Manager, with OSAC's Kubernetes Manager for each network type it declares, against shared networking behavior. The required profiles follow the services enabled in the lab, so a provider that offers only VMs needs only the VM profile; a workload service's networking is supported only with a conformant report whose profile for that service passed (OSAC does not enforce this).
- **FR-10:** OSAC retries failed networking work safely and runs at most one job at a time per resource (or workload interface), task, and manager, so later work never overlaps earlier work on the same resource. A retry neither duplicates nor removes active backend state.
- **FR-11:** A Cloud Infrastructure Admin can run the published conformance suite against a Fabric Manager and get pass, fail, or skip per test and an overall result, conformant or in progress; a skipped required test is never a pass.
- **FR-12:** Supported workload interfaces get tenant IPv4 configuration through DHCP from the manager that owns them. OSAC computes each Subnet's address layout once at creation, from the provider's address plan, and each manager allocates only from its range, so VM and bare-metal addresses on a shared Subnet never overlap. A range the plan leaves empty is an empty list, and OSAC never allocates from it. [Unified Networking PRD: FR-1]
- **FR-13:** Both managers enforce SecurityGroups, each at its own enforcement point (Kubernetes: VM pods; Fabric: bare-metal ports and VM addresses), exactly as the rules say or, where the contract allows it (never on a bare-metal port), as a documented no-op, not at all, and never allow more. Each creates one stateful policy object per group and binds the interfaces it handles to their selected groups (a VM pod before the VM exists, a bare-metal port before it carries tenant traffic, a VM address once it is known); when a tenant updates a group's rules, each manager replaces them in its object, and every bound interface follows.
- **FR-14:** VM provisioning starts only after the Kubernetes Manager applied the VM's NetworkAttachment: VMaaS creates the VM with its requested network already configured, so its first boot uses that network.

### 4.2 Non-Functional Requirements

None.

## 5. Dependencies

- **Unified Networking:** the shared resources, tenant-visible behavior, and SecurityGroup semantics that every conforming implementation preserves.
- **Manager designs:** each manager's settings, network types, limits, prerequisites, and hub permissions.
- **Workload service designs:** when each service creates and deletes NetworkAttachments and how it uses manager results.
- **Manager implementations:** provider Fabric Managers; OSAC's Kubernetes Managers (this release: `cudn_evpn`).

---

## Provenance

Authored: revise @ prd 0.11.5 - a58bdf7, workspace docs/unified-networking-docs-structure @ 64da781
Final: revise @ prd 0.11.5 - a58bdf7, workspace docs/unified-networking-docs-structure @ 64da781 (dirty)

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"a58bdf7","source_repo":"64da781 (dirty)","source_repo_branch":"docs/unified-networking-docs-structure","commits_behind_main":0,"commits_ahead_main":60,"main_ref":"main","phases":["revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
