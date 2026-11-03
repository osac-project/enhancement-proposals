---
title: bmaas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-11-03
see-also:
  - Unified Networking PRD: /enhancements/OSAC-1433-unified-networking/prd.md
  - BMaaS Networking Design: /enhancements/OSAC-1437-bmaas-networking/design.md
  - BMaaS Networking Test Plan (design section): /enhancements/OSAC-1437-bmaas-networking/design.md#test-plan
replaces:
  - N/A
superseded-by:
  - N/A
---

# BMaaS Networking — Single Attachment and Automatic External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Date        | 2026-11-03 |

This PRD extends the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md) for bare-metal servers and inherits its [deployment](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary) and [hub](/enhancements/OSAC-1433-unified-networking/design.md#networking-hub-support-boundary) support boundaries and [create/read/delete contract, with its SecurityGroup rule update](/enhancements/OSAC-1433-unified-networking/prd.md#fr-8-createreaddelete-networking-contract-r8). A server's network selection is fixed at creation; to change it, replace the server.

Provider-dependent connectivity, allocation, and cleanup in this document apply with provider networking enabled; FR-13 covers provider networking disabled. Default SecurityGroup selection, immutability, validation, and dependency rules apply in both cases.

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
    - [Physical Interface Discovery](#physical-interface-discovery)
    - [Interface Validation](#interface-validation)
    - [Primary Gateway Designation](#primary-gateway-designation)
    - [Optional Network Attachment with Defaults](#optional-network-attachment-with-defaults)
    - [Automatic External Access](#automatic-external-access)
    - [Network Connectivity Configuration](#network-connectivity-configuration)
    - [IP Address Discovery](#ip-address-discovery)
    - [External IP Attachment for Bare-Metal](#external-ip-attachment-for-bare-metal)
    - [Provider Networking Selection](#provider-networking-selection)
    - [Automatic Resource Cleanup](#automatic-resource-cleanup)
    - [Network Attachment Deletion](#network-attachment-deletion)
    - [Provider Networking Disabled](#provider-networking-disabled)
    - [Stateful Attachment Policy](#stateful-attachment-policy)
  - [4.2 Non-Functional Requirements](#42-non-functional-requirements)
- [5. Acceptance Criteria](#5-acceptance-criteria)
- [6. Assumptions](#6-assumptions)
- [7. Dependencies](#7-dependencies)

## 1. Problem Statement

Provisioning bare-metal servers requires manual switch configuration outside the OSAC API. Tenants cannot attach servers to Subnets, apply SecurityGroups, or configure external access through the API, and must learn physical interface names from out-of-band documentation. A reachable server with inbound and outbound connectivity takes sequential API calls plus manual switch-port coordination with infrastructure administrators.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can provision a bare-metal server with one explicit network attachment, optionally choosing the physical interface that connects to its Subnet
- A tenant can create a server with `--external-ip-attachment` and get an ExternalIP for inbound access automatically
- Network attachments are optional; when omitted, the server uses the tenant's default Subnet and SecurityGroup
- Tenants and administrators can discover each server type's physical interfaces and which can carry tenant traffic
- Servers get tenant connectivity on the selected interface after host provisioning
- ExternalIPAttachments can target bare-metal servers
- Cloud Infrastructure Admins select the deployment's networking implementation without exposing provider selection to tenants

### 2.2 Non-Goals

- Cluster or VM networking (separate enhancements)
- Provider-specific networking implementation; this PRD defines bare-metal outcomes on the shared networking and manager contracts
- Multi-interface failover or bonding
- Enabling bare-metal servers on a deployment that already has networking resources ([Unified — Subnet address plan](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-plan))

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a bare-metal server with one explicit network attachment so that I can connect a selected physical interface to a Subnet
- As a Tenant User, I want to see the physical network ports of a BareMetalInstanceType so that I can select the right interface for the attachment
- As a Tenant User, I want to create a server with `--external-ip-attachment` and have it externally reachable in one API call, without creating ExternalIP and ExternalIPAttachment resources myself
- As a Tenant User, I want the sole network attachment to provide the default gateway without a second attachment, so that traffic has one unambiguous primary route
- As a Tenant User, I want automatic ExternalIPs cleaned up when I delete the server, so that I do not accumulate orphaned resources
- As a Tenant User, I want a clear error if I select a port that does not exist or is not tenant-attachable, so that I can correct the request before provisioning starts

### Tenant Admin Stories

- As a Tenant Admin, I want to see which physical interfaces of a server connect to which Subnets so that I can troubleshoot connectivity

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to define which physical interfaces of each server type are available for tenant networking, so tenants can choose a suitable connection
- As a Cloud Infrastructure Admin, I want bare-metal networking to use the deployment's selected networking implementation, so that tenants do not choose a provider backend

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want to see the IP addresses allocated to each network interface of a server so that I can troubleshoot connectivity and external access

## 4. Requirements

### 4.1 Functional Requirements

#### Network Attachment

- **FR-1:** A tenant can create a bare-metal server with at most one network attachment ([Unified PRD FR-7](/enhancements/OSAC-1433-unified-networking/prd.md#fr-7-single-network-attachment-per-workload-r7)); requests for more are rejected. The tenant can leave network choices to the platform or give a partial selection (FR-5); the resolved selection is fixed after creation.

#### Physical Interface Discovery

- **FR-2:** Tenants and administrators can discover each bare-metal instance type's network interfaces, including what distinguishes tenant-facing from system interfaces. When several suitable tenant-facing interfaces exist, the platform picks a consistent default.

#### Interface Validation

- **FR-3:** OSAC rejects a request that selects an unavailable or system-only interface, or that attaches a server to multiple tenant networks, with an error identifying the invalid choice.

#### Primary Gateway Designation

- **FR-4:** The server's sole network attachment is its primary route and gateway; there is no separate primary-network choice.

#### Optional Network Attachment with Defaults

- **FR-5:** Network selection is optional. OSAC resolves an omitted or partial Subnet and SecurityGroup selection as [Default Networking PRD FR-6](/enhancements/OSAC-1433-default-networking/prd.md#optional-network-attachment-with-defaults) defines and, when no interface is given, selects a suitable tenant-facing interface for the server's instance type. The resolved network stays visible with the server after creation.

#### Automatic External Access

- **FR-6:** A tenant can request `--external-ip-attachment` when creating a bare-metal server; the server is its only endpoint. Capacity check, readiness, visibility, and behavior with provider networking disabled follow [Default Networking PRD FR-8 to FR-11](/enhancements/OSAC-1433-default-networking/prd.md#automatic-external-access): inbound access starts only after the provider assigns a real address and the server's tenant endpoint is ready.

#### Network Connectivity Configuration

- **FR-7:** With provider networking enabled, the server gets tenant connectivity on the selected interface after host provisioning. OSAC reports it only after the attachment is ready and the selected interface has a known tenant address; policy is active before traffic. A provisioning-network address is never presented as the tenant address.

#### IP Address Discovery

- **FR-8:** The tenant IPv4 address of the selected interface is visible with the server after discovery. If the platform cannot identify that interface or its address, it reports the issue clearly and never substitutes an address from another interface or from host provisioning.

#### External IP Attachment for Bare-Metal

- **FR-9:** An ExternalIPAttachment can provide inbound access to a bare-metal server; traffic to its ExternalIP reaches the server's primary tenant address.

#### Provider Networking Selection

- **FR-10:** Bare-metal networking uses the networking implementation the Cloud Infrastructure Admin selects; tenants neither select nor need to understand it ([Unified PRD FR-6](/enhancements/OSAC-1433-unified-networking/prd.md#fr-6-modular-networking-backends-with-transparent-selection-r6)).

#### Automatic Resource Cleanup

- **FR-11:** Deleting a server removes its automatically created inbound routes and external addresses. If provider cleanup fails, deletion stays pending with an actionable diagnostic and the resources stay owned for retry. The tenant removes manually created routes first; shared tenant defaults remain.

#### Network Attachment Deletion

- **FR-12:** Server deletion returns a host to the available inventory only after required tenant-network cleanup completes and the host is safe to reuse; a cleanup failure keeps deletion pending and visible. A host that an east-west domain may still include stays out of the available inventory until the Cloud Provider Admin repairs it.

#### Provider Networking Disabled

- **FR-13:** A Cloud Provider Admin can install a deployment with provider networking disabled ([Unified PRD FR-10](/enhancements/OSAC-1433-unified-networking/prd.md#fr-10-provider-networking-control-at-installation)); bare-metal host provisioning, management, and deprovisioning stay available. With provider networking disabled, OSAC does not move tenant interfaces, discover tenant addresses, or promise tenant routing or ExternalIP access; the service keeps using the platform's provisioning network when its other requirements are met. Networking API status makes clear that provider work is not done, and deletion stays available (FR-12).

#### Stateful Attachment Policy

- **FR-14:** The selected SecurityGroups form the server's policy ([Unified PRD FR-1](/enhancements/OSAC-1433-unified-networking/prd.md#fr-1-network-isolation-and-connectivity-r1)). Policy is active before traffic (FR-7), and policy failures are visible.

### 4.2 Non-Functional Requirements

Beyond the [Unified PRD](/enhancements/OSAC-1433-unified-networking/prd.md): FR-6 covers the capacity check and its clear error, and:

- **NFR-1:** More than 95% of bare-metal servers created with provider networking enabled and completed OS provisioning reach `Ready` with a tenant IPv4 address. Measure the rate over the eligible server cohort; the reporting window and source metric are TBD.

- **NFR-2:** OSAC continues tenant-address discovery until it finds an address or reports a terminal failure, and exposes the latest discovery result to the tenant. Connectivity and discovery latency targets are TBD pending measurements with a conformant Fabric Manager.

## 5. Acceptance Criteria

- [ ] A Tenant User can create a bare-metal server with one network attachment and, when needed, select an available tenant-facing interface
- [ ] A Tenant User can create a server with `--external-ip-attachment` and no network selection; OSAC uses the tenant defaults and provides inbound access once the server and address are ready
- [ ] The server's sole network attachment provides its primary route, and its tenant address is visible after connectivity is established
- [ ] Available physical interfaces are discoverable; unavailable or system-only interfaces are rejected with a clear error
- [ ] With provider networking enabled, deletion keeps the host unavailable for reuse until required network and ExternalIP cleanup completes; after provider repair, deletion continues without losing resource ownership
- [ ] Automatic ExternalIPs and ExternalIPAttachments are visible and are removed when their server is deleted
- [ ] An ExternalIPAttachment can target a bare-metal server and sends inbound traffic to its primary tenant address
- [ ] A policy application failure leaves the server non-ready; a missing selected-interface identity does not expose a provisioning or another-interface address
- [ ] Default SecurityGroup resolution, invalid network/interface rejection, tenant boundaries, and network immutability remain active with provider networking enabled or disabled
- [ ] With provider networking disabled, host provisioning works when platform prerequisites are met; server readiness does not imply tenant routing, external-address allocation, or provider cleanup
- [ ] With provider networking disabled, deletion and host deprovisioning stay available
- [ ] An automatic external-access request accepted while provider networking is disabled exposes no fabricated address or route and never gives that server inbound access
- [ ] Update rules meet [Unified PRD FR-8](/enhancements/OSAC-1433-unified-networking/prd.md#fr-8-createreaddelete-networking-contract-r8) for bare-metal servers

## 6. Assumptions

- The tenant's default networking resources (VirtualNetwork, Subnet, SecurityGroup) are pre-created at onboarding (see Default Networking PRD). Without them, creating a server without network attachments fails with a clear error.
- The NetworkClass selects a registered Fabric Manager.
- Every Subnet has the address range the service needs, because the provider's address plan covers every enabled service ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-plan)).
- The selected instance type exposes at least one suitable tenant-facing interface; otherwise creating a server fails with a clear error.
- Only ports whose port role is `fabric` can be selected for tenant networking; `management`, `storage`, and `lifecycle` (BMC) ports cannot.

## 7. Dependencies

- **Unified Networking design** — the unified networking resource model ([Unified Networking design](/enhancements/OSAC-1433-unified-networking/design.md))
- **Default Networking PRD** — default Subnet and SecurityGroup selection ([Default Networking PRD](/enhancements/OSAC-1433-default-networking/prd.md))
- **Network Manager Integration Contract** — manager selection, shared task execution, and the requirements a provider's Fabric Manager must meet; this PRD defines bare-metal behavior on top of it ([PRD](/enhancements/OSAC-1433-network-manager-integration-contract-networking/prd.md), [design](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md))
- **NATGateway stack** — outbound access for servers through the VirtualNetwork's NATGateway
- **Conformant Fabric Manager** — has a conformant report from the shared conformance suite whose `baremetal` profile passed; see [design risks and mitigations](design.md#risks-and-mitigations)

---
