---
title: vmaas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-10-22
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1435
see-also:
  - Unified Networking PRD: /enhancements/OSAC-1433-unified-networking/prd.md
  - VMaaS Networking Design: /enhancements/OSAC-1435-vmaas-networking/design.md
replaces:
  - N/A
superseded-by:
  - N/A
---

# VMaaS Networking — Single Attachment VMs and Automatic External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1435 |
| Date        | 2026-10-22 |

This PRD extends the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md) for VMs and inherits its [deployment](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary) and [hub](/enhancements/OSAC-1433-unified-networking/design.md#networking-hub-support-boundary) support boundaries and [create/read/delete contract, with its SecurityGroup rule update](/enhancements/OSAC-1433-unified-networking/prd.md#fr-8-createreaddelete-networking-contract-r8). A VM's network selection is fixed at creation; to change it, replace the VM. Connectivity, allocation, and cleanup described here apply with provider networking enabled; FR-7 covers provider networking disabled. Validation, default SecurityGroup selection, immutability, and dependency rules apply in both cases.

## Contents

- [1. Problem Statement](#1-problem-statement)
- [2. Goals and Non-Goals](#2-goals-and-non-goals)
  - [2.1 Goals](#21-goals)
  - [2.2 Non-Goals](#22-non-goals)
- [3. User Stories](#3-user-stories)
  - [Tenant User Stories](#tenant-user-stories)
  - [Tenant Admin Stories](#tenant-admin-stories)
  - [Cloud Infrastructure Admin Stories](#cloud-infrastructure-admin-stories)
  - [Cloud Provider Admin Stories](#cloud-provider-admin-stories)
- [4. Requirements](#4-requirements)
  - [4.1 Functional Requirements](#41-functional-requirements)
    - [Network Attachment](#network-attachment)
    - [Optional Network Attachment with Defaults](#optional-network-attachment-with-defaults)
    - [Automatic External Access](#automatic-external-access)
    - [IP Address Discovery](#ip-address-discovery)
    - [Deployment Validation](#deployment-validation)
    - [Compatibility](#compatibility)
    - [Provider Networking Disabled](#provider-networking-disabled)
    - [Stateful Attachment Policy](#stateful-attachment-policy)
    - [VM Network Preparation](#vm-network-preparation)
  - [4.2 Non-Functional Requirements](#42-non-functional-requirements)
- [5. Acceptance Criteria](#5-acceptance-criteria)
- [6. Assumptions](#6-assumptions)
- [7. Dependencies](#7-dependencies)
- [8. Risks](#8-risks)
  - [8.1 Virtualization platform integration blocked or delayed](#81-virtualization-platform-integration-blocked-or-delayed)
  - [8.2 Shared manager contract not implemented](#82-shared-manager-contract-not-implemented)
  - [8.3 ExternalIPPool exhaustion](#83-externalippool-exhaustion)

## 1. Problem Statement

Creating a VM with external access requires manual IP allocation and NAT configuration, so tenants must understand inbound and outbound routing before their first reachable VM. VMs also need explicit networking details on every create, while other resource types have simplified creation flows.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can create a VM with zero or one network attachment; that attachment is the primary/default route
- A tenant can create a VM with `--external-ip-attachment` and get an ExternalIP allocated and attached automatically for inbound access
- A tenant can create a VM without networking details; the system uses the tenant's default Subnet and SecurityGroup
- The platform prevents VM creation in deployments that do not support virtualization

### 2.2 Non-Goals

- Cluster or bare-metal server networking (separate enhancements)
- More than one network attachment per VM

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a VM with one network attachment, so that it gets connectivity on the selected Subnet
- As a Tenant User, I want the VM's sole network attachment to provide its default gateway and DNS configuration without a separate primary-network choice
- As a Tenant User, I want to create a VM with `--external-ip-attachment`, so that it is externally reachable without manually allocating an IP
- As a Tenant User, I want to create a VM without network details, so that the system uses my default Subnet and SecurityGroup and I can start quickly
- As a Tenant User, I want a clear error when I create a VM in a deployment without a Kubernetes Manager, so that I understand the limitation and can choose a different deployment

### Tenant Admin Stories

- As a Tenant Admin, I want to inspect the default Subnet and SecurityGroup used for VMs created without network configuration, and create replacements when I need different settings
- As a Tenant Admin, I want to see each VM's Subnet, SecurityGroups, and per-interface IP address, so I can audit my organization's network topology

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to configure which deployments support VMs, so that VM creation in deployments without a Kubernetes Manager is rejected with a clear error
- As a Cloud Infrastructure Admin, I want to see automatic ExternalIPs, so I can monitor capacity and troubleshoot connectivity

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want to install with provider networking disabled while VMs keep platform connectivity, so that I can run VMaaS without provider network configuration

## 4. Requirements

### 4.1 Functional Requirements

#### Network Attachment

- **FR-1:** A VM has at most one network attachment ([Unified PRD FR-7](/enhancements/OSAC-1433-unified-networking/prd.md#fr-7-single-network-attachment-per-workload-r7)); OSAC rejects more. That attachment is primary: it supplies the default route and the network context for inbound access, with no separate primary-network choice. Optional outbound translation comes from the selected VirtualNetwork's NATGateway.

#### Optional Network Attachment with Defaults

- **FR-2:** Network configuration is optional when creating a VM. OSAC resolves an omitted or partial selection as [Default Networking PRD FR-6](/enhancements/OSAC-1433-default-networking/prd.md#optional-network-attachment-with-defaults) defines, and the VM's resolved network is visible after creation.

#### Automatic External Access

- **FR-3:** A tenant can request `--external-ip-attachment` when creating a VM; the VM is its only endpoint. Capacity check, readiness, visibility, and cleanup follow [Default Networking PRD FR-8 to FR-11](/enhancements/OSAC-1433-default-networking/prd.md#automatic-external-access): inbound access starts only after the provider assigns a real address and the VM endpoint is ready.

#### IP Address Discovery

- **FR-4:** After provisioning, the VM status shows the network attachment's IP address. Inbound traffic to an ExternalIP attached to the VM is routed to that attachment's IP.

#### Deployment Validation

- **FR-5:** VM creation fails with a clear error that explains the target deployment does not support virtualization (a deployment without a Kubernetes Manager).

#### Compatibility

- **FR-6:** Upgrade follows [Unified — Upgrade and Downgrade Strategy](/enhancements/OSAC-1433-unified-networking/design.md#upgrade-and-downgrade-strategy).

#### Provider Networking Disabled

- **FR-7:** A Cloud Provider Admin can install a deployment with provider networking disabled ([Unified PRD FR-10](/enhancements/OSAC-1433-unified-networking/prd.md#fr-10-provider-networking-control-at-installation)); ordinary VM provisioning and the networking APIs stay available. With provider networking disabled, ordinary VMs can use the platform's default connectivity, and OSAC never claims that a tenant Subnet, ExternalIP, or provider route was configured. An `--external-ip-attachment` request accepted while provider networking is disabled does not block VM provisioning and never gives that VM external access. VM deletion stays available.

#### Stateful Attachment Policy

- **FR-8:** A VM's selected SecurityGroups form its policy ([Unified PRD FR-1](/enhancements/OSAC-1433-unified-networking/prd.md#fr-1-network-isolation-and-connectivity-r1)). OSAC reports tenant connectivity only after the attachment is ready on every enforcement point and the tenant address is known; policy is active before traffic. A policy failure is visible and never reported as successful connectivity.

#### VM Network Preparation

- **FR-9:** OSAC prepares the VM's network attachment before creating the VM, so its first boot uses the requested network.

### 4.2 Non-Functional Requirements

None beyond the [Unified PRD](/enhancements/OSAC-1433-unified-networking/prd.md); FR-3 covers the capacity check and its clear error.

## 5. Acceptance Criteria

- [ ] A Tenant User can create a VM with zero or one `--network-attachment` flag; a second flag is rejected with a clear maximum-one error
- [ ] A VM with one attachment gets its default gateway from that attachment
- [ ] A VM created with an omitted or empty attachment list gets the tenant defaults
- [ ] A VM created with a partial network selection gets defaults only for the missing choices
- [ ] A Tenant User can create a VM with `--external-ip-attachment` and no network configuration; the VM is on the default Subnet with an automatic ExternalIP for inbound access
- [ ] Automatic ExternalIPs and ExternalIPAttachments appear in list views with the label `osac.openshift.io/auto-created`
- [ ] Deleting a VM with an automatic ExternalIP removes the automatic ExternalIP and ExternalIPAttachment
- [ ] Persistent automatic external cleanup failure leaves VM deletion pending with a diagnostic until repair, then resumes without losing address ownership
- [ ] After provisioning, VM status shows the allocated IP address of its network attachment
- [ ] Two VMs in one Subnet with different groups get their own stateful policies before traffic; a policy failure leaves the affected VM non-ready
- [ ] VMaaS creates a VM only after its network attachment is ready, and the VM's first boot uses that network
- [ ] An ExternalIPAttachment targeting a VM routes inbound traffic to the VM's primary attachment IP
- [ ] Creating a VM in a deployment without a Kubernetes Manager returns a clear error
- [ ] Default SecurityGroup resolution, invalid-reference/non-ready-dependency rejection, tenant boundaries, and the interface, cardinality, and immutability rules stay active
- [ ] With provider networking disabled, ordinary VM provisioning works on platform connectivity, and API results do not imply tenant-network connectivity, inbound access, or provider-side cleanup
- [ ] With provider networking disabled, deletion keeps dependency and cascade order and runs no provider cleanup; ordinary workload deletion stays available
- [ ] With provider networking disabled, an automatic external-address request does not block VM provisioning; OSAC exposes no fabricated address or inbound attachment, and that VM never gets inbound access
- [ ] Update rules meet [Unified PRD FR-8](/enhancements/OSAC-1433-unified-networking/prd.md#fr-8-createreaddelete-networking-contract-r8) for VMs

## 6. Assumptions

- The platform pre-creates the tenant's default networking resources (VirtualNetwork, Subnet, SecurityGroup) (see Default Networking PRD). Without them, creating a VM without network configuration fails with a clear error.
- The target deployment supports virtualization; deployments without a Kubernetes Manager do not support VMs.
- Every Subnet has the address range the service needs, because the provider's address plan covers every enabled service ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-plan)).

## 7. Dependencies

- **Unified Networking design** — the networking resource model ([Unified Networking design](/enhancements/OSAC-1433-unified-networking/design.md))
- **Default Networking PRD** — default Subnet and SecurityGroup selection ([Default Networking PRD](/enhancements/OSAC-1433-default-networking/prd.md))
- **Network Manager Integration Contract** — manager registration, task execution, and shared networking behavior that this PRD's VM behavior uses ([PRD](/enhancements/OSAC-1433-network-manager-integration-contract-networking/prd.md), [design](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md))
- **OSAC-1712 (automatic pool selection)** — the automatic ExternalIP pool choice ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access))
- **OSAC Kubernetes Manager** (this release: `cudn_evpn`) — see Risk 8.1.

## 8. Risks

### 8.1 Virtualization platform integration blocked or delayed

- **Owner:** Engineering / Product
- **Mitigation:** Without an OSAC Kubernetes Manager, VM creation is rejected; a Fabric Manager that lacks its network type makes the NetworkClass FAILED, so no networking resource can be created.

### 8.2 Shared manager contract not implemented

- **Owner:** Platform team
- **Mitigation:** Deliver the shared manager registration, task execution, result validation, and recovery behavior before enabling provider-backed VM networking.

### 8.3 ExternalIPPool exhaustion

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** Pool capacity is visible in status; the error tells the tenant to contact the admin.

---

## Provenance

Authored: revise @ prd 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)
Final: manual-edit [manual] @ prd 0.11.5 - 0c7ea35, workspace main @ 14c4d6f1c (17 behind origin/main)

> Context changed between revise and manual-edit.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"0c7ea35","source_repo":"14c4d6f1c","source_repo_branch":"main","commits_behind_main":17,"commits_ahead_main":0,"main_ref":"main","phases":["revise","manual-edit","revise","manual-edit","revise","manual-edit","revise","respond","revise","manual-edit"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
