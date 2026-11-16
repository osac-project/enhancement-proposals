---
title: vmaas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-11-16
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1435
  - https://redhat.atlassian.net/browse/OSAC-6121
see-also:
  - Unified Networking PRD: /enhancements/OSAC-1433-unified-networking/prd.md
  - VMaaS Networking Design: /enhancements/OSAC-1435-vmaas-networking/design.md
replaces:
  - N/A
superseded-by:
  - N/A
---

# VMaaS Networking — Multi-NIC VMs and Automatic External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1435, https://redhat.atlassian.net/browse/OSAC-6121 (multi-NIC) |
| Date        | 2026-11-16 |

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
    - [Multiple Interfaces](#multiple-interfaces)
    - [Network Kinds](#network-kinds)
    - [Management Network](#management-network)
  - [4.2 Non-Functional Requirements](#42-non-functional-requirements)
- [5. Acceptance Criteria](#5-acceptance-criteria)
- [6. Assumptions](#6-assumptions)
- [7. Dependencies](#7-dependencies)
- [8. Risks](#8-risks)
  - [8.1 Virtualization platform integration blocked or delayed](#81-virtualization-platform-integration-blocked-or-delayed)
  - [8.2 Shared manager contract not implemented](#82-shared-manager-contract-not-implemented)
  - [8.3 ExternalIPPool exhaustion](#83-externalippool-exhaustion)
  - [8.4 Fabric overlay networks cannot yet be extra interfaces](#84-fabric-overlay-networks-cannot-yet-be-extra-interfaces)

## 1. Problem Statement

Creating a VM with external access requires manual IP allocation and NAT configuration, so tenants must understand inbound and outbound routing before their first reachable VM. VMs also need explicit networking details on every create, while other resource types have simplified creation flows.

Real workloads also need more than one network interface. Appliances, routers and storage clients keep traffic types apart on separate interfaces, and providers often need to reach every VM through a separate management network, whatever networks its owner chose. Providers build tenant networks with different technologies, such as a fabric-wide overlay or a physical VLAN handed to the hosts, each with different limits, so a tenant needs to know which networks a VM can use as its main interface and which only as an extra one.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can create a VM with several network attachments, up to eight interfaces per VM; exactly one is the primary and carries the default route
- A provider can offer several kinds of networks, and a tenant chooses the kind when creating a network
- A provider can run a management network that every VM is connected to automatically, reachable only from the provider's management systems, with each tenant on its own part of the network
- A tenant can create a VM with `--external-ip-attachment` and get an ExternalIP allocated and attached automatically for inbound access
- A tenant can create a VM without networking details; the system uses the tenant's default Subnet and SecurityGroup
- The platform prevents VM creation in deployments that do not support virtualization

### 2.2 Non-Goals

- Cluster or bare-metal server networking (separate enhancements)
- Adding or removing a VM's interfaces after creation
- IPv6 or dual-stack addressing
- A multi-interface step in the tenant UI VM wizard; the UI shows every interface of a VM
- High-performance pass-through network devices
- A physical VLAN network as a VM's main interface, and deployments without the fabric overlay
- Separate billing of network interfaces

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a VM with one network attachment, so that it gets connectivity on the selected Subnet
- As a Tenant User, I want to create a VM with several network attachments on different networks, so that my workload keeps its traffic types apart
- As a Tenant User, I want to choose which interface is the main one, so that the default gateway, DNS, outbound access and external addresses use it; a VM with one attachment uses it without a choice
- As a Tenant User, I want to create a VM with `--external-ip-attachment`, so that it is externally reachable without manually allocating an IP
- As a Tenant User, I want to create a VM without network details, so that the system uses my default Subnet and SecurityGroup and I can start quickly
- As a Tenant User, I want my VM to work on my own networks even when its management interface is not working, so that a provider-side problem does not block my workload
- As a Tenant User, I want a clear error when I create a VM in a deployment without a Kubernetes Manager, so that I understand the limitation and can choose a different deployment

### Tenant Admin Stories

- As a Tenant Admin, I want to inspect the default Subnet and SecurityGroup used for VMs created without network configuration, and create replacements when I need different settings
- As a Tenant Admin, I want to see each VM's interfaces with their Subnet, SecurityGroups, IP address and hardware address, so I can audit my organization's network topology

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to configure which deployments support VMs, so that VM creation in deployments without a Kubernetes Manager is rejected with a clear error
- As a Cloud Infrastructure Admin, I want to see automatic ExternalIPs, so I can monitor capacity and troubleshoot connectivity
- As a Cloud Infrastructure Admin, I want to offer several kinds of tenant networks, each stating whether it can be a VM's main or extra interface, so tenants pick a network that works
- As a Cloud Infrastructure Admin, I want every VM connected to my management network without the tenant asking, so my management systems reach the VMs while VMs never reach each other over it and tenants never share a segment
- As a Cloud Infrastructure Admin, I want to see which VMs my management systems cannot reach, so I can act on them

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want to install with provider networking disabled while VMs keep platform connectivity, so that I can run VMaaS without provider network configuration

## 4. Requirements

### 4.1 Functional Requirements

#### Network Attachment

- **FR-1:** A VM has up to eight interfaces, each on a Subnet the tenant can use and each with a name unique within the VM; OSAC rejects more. In a deployment with a management network, one of the eight is the management interface (FR-12), so a tenant chooses up to seven. This extends [Unified PRD FR-7](/enhancements/OSAC-1433-unified-networking/prd.md#fr-7-network-attachments-per-workload-r7) for VMs; other workloads keep one attachment. Exactly one attachment is primary: it supplies the default route and the network context for inbound access, and optional outbound translation comes from its VirtualNetwork's NATGateway. A single attachment is primary without a choice; with several, the tenant marks the primary.

#### Optional Network Attachment with Defaults

- **FR-2:** Network configuration is optional when creating a VM. OSAC resolves an omitted or partial selection as [Default Networking PRD FR-6](/enhancements/OSAC-1433-default-networking/prd.md#optional-network-attachment-with-defaults) defines, and the VM's resolved network is visible after creation.

#### Automatic External Access

- **FR-3:** A tenant can request `--external-ip-attachment` when creating a VM; the VM is its only endpoint. Capacity check, readiness, visibility, and cleanup follow [Default Networking PRD FR-8 to FR-11](/enhancements/OSAC-1433-default-networking/prd.md#automatic-external-access): inbound access starts only after the provider assigns a real address and the VM endpoint is ready.

#### IP Address Discovery

- **FR-4:** After provisioning, the VM status shows each network attachment's name, Subnet, IP address, hardware address and whether it is primary, and the tenant UI's VM details show the same list. Each address stays the same across VM restart and migration. Inbound traffic to an ExternalIP attached to the VM is routed to the primary attachment's IP.

#### Deployment Validation

- **FR-5:** VM creation fails with a clear error that explains the target deployment does not support virtualization (a deployment without a Kubernetes Manager).

#### Compatibility

- **FR-6:** Upgrade follows [Unified — Upgrade and Downgrade Strategy](/enhancements/OSAC-1433-unified-networking/design.md#upgrade-and-downgrade-strategy).

#### Provider Networking Disabled

- **FR-7:** A Cloud Provider Admin can install a deployment with provider networking disabled ([Unified PRD FR-10](/enhancements/OSAC-1433-unified-networking/prd.md#fr-10-provider-networking-control-at-installation)); ordinary VM provisioning and the networking APIs stay available, and no management interface is added. With provider networking disabled, ordinary VMs can use the platform's default connectivity, and OSAC never claims that a tenant Subnet, ExternalIP, or provider route was configured. An `--external-ip-attachment` request accepted while provider networking is disabled does not block VM provisioning and never gives that VM external access. VM deletion stays available.

#### Stateful Attachment Policy

- **FR-8:** Each attachment's selected SecurityGroups form that interface's policy ([Unified PRD FR-1](/enhancements/OSAC-1433-unified-networking/prd.md#fr-1-network-isolation-and-connectivity-r1)) and do not affect the VM's other interfaces. OSAC reports tenant connectivity only after every attachment the tenant chose is ready on every enforcement point and every tenant address is known; policy is active before traffic. A policy failure is visible and never reported as successful connectivity. Accepted limit: on network kinds without address enforcement (the physical VLAN networks of this release, including the management network), a VM can send traffic that claims another address of the same network, so a SecurityGroup rule that admits a source address range does not stop such traffic from other VMs of that tenant on that network; such a network carries only one tenant's VMs, so this never involves other tenants.

#### VM Network Preparation

- **FR-9:** OSAC prepares every network attachment of the VM before creating the VM, so its first boot uses the requested networks: each interface gets its address automatically, an extra interface reaches its own network and the destinations routed through it, and only the primary interface carries default traffic.

#### Multiple Interfaces

- **FR-10:** A request the deployment cannot build is rejected when the VM is created, before anything is provisioned, with an error that names the broken rule: more interfaces than allowed, no primary or more than one, duplicate interface names, a network kind that cannot serve the requested position, an image that does not support several interfaces, or two interfaces the deployment cannot combine on one VM. A VM's interfaces cannot change after creation.

#### Network Kinds

- **FR-11:** A Cloud Infrastructure Admin can offer several kinds of networks with different underlying implementations; each kind states whether it can be a VM's main interface, an extra interface, or both. Kinds are named and described by what they offer, never by how they are built. A tenant user lists the offered kinds and chooses one when creating a network, or gets the provider's default kind without choosing. A new kind of network implementation is added through provider configuration and an OSAC network implementation, without changing how tenants request VMs and networks.

#### Management Network

- **FR-12:** A Cloud Infrastructure Admin can configure one management network for the deployment. Every tenant gets its own segment of it, without asking. On it, a VM accepts traffic only from, and sends traffic only to, the provider's management systems; a VM never exchanges traffic with another VM over it, in its own tenant or another; VMs of different tenants never share a segment, and a VM cannot send traffic that appears to come from another tenant or from a management system; tenants cannot change or remove it. Accepted limit (FR-8): within one tenant's segment, a VM can claim another VM's address toward the provider's systems, and VMs on it can see which addresses of the segment are in use, so those systems identify the tenant by its segment and a VM through the provider's administration interface, not by address alone.
- **FR-13:** In a deployment with a working management network, OSAC adds a management interface to every VM a tenant creates, however it is requested (VMs that OSAC creates as cluster workers are out of scope here). Tenants do not ask for it and cannot add, change or remove it. VMs that exist before the management network works do not get one.
- **FR-14:** OSAC prepares the management interface before it creates the VM, like every interface (FR-9). Once the VM is created, the management interface never blocks the tenant's use of it: a VM whose own interfaces are ready is reported ready, and gets its external access, even when its management interface has no address or its provider-side setup failed. The state of each VM's management interface is visible, so the provider can find VMs it cannot reach.
- **FR-15:** While a tenant's management segment is not ready, VM creation for that tenant fails with a clear error that says whether to wait or to contact the provider, and the tenant's status shows it. A tenant can have as many VMs as its management segment has addresses; the provider chooses that size at installation, and a create beyond it fails with a clear error.

### 4.2 Non-Functional Requirements

None beyond the [Unified PRD](/enhancements/OSAC-1433-unified-networking/prd.md); FR-3 covers the capacity check and its clear error.

## 5. Acceptance Criteria

- [ ] A Tenant User can create a VM with zero to eight `--network-attachment` flags (seven in a deployment with a management network); one more is rejected with a clear error stating the maximum
- [ ] A VM with one attachment gets its default gateway from that attachment
- [ ] A VM with a primary and two extra attachments on networks of different kinds gets an address on each; default traffic leaves through the primary and each extra interface reaches its own network
- [ ] Requests with no primary, several primaries, duplicate names, or a network kind in a position it does not support are rejected at creation, naming the rule, and nothing is provisioned
- [ ] A tenant lists the offered network kinds and creates a network of a chosen kind; a tenant cannot create a network of the provider management kind
- [ ] A VM created with no network details in a deployment with a management network has a management interface; the provider's management system reaches the VM through it, and another VM on the management network, of the same or another tenant, does not
- [ ] Every tenant has its own management network segment without creating it, and cannot change, delete or attach to it
- [ ] A VM cannot send traffic on the management network that appears to come from another tenant or from a management system
- [ ] A VM whose image ignores the management interface is reported ready and gets its external access, and its management interface is shown as not ready
- [ ] While a tenant's management segment is not ready, its VM creates fail with a clear error, and the tenant status shows the cause
- [ ] A VM create beyond the size of the tenant's management segment fails with a clear error
- [ ] SecurityGroups on one interface do not affect traffic on another
- [ ] A VM keeps every interface address after a restart and a live migration
- [ ] A VM created with an omitted or empty attachment list gets the tenant defaults
- [ ] A VM created with a partial network selection gets defaults only for the missing choices
- [ ] A Tenant User can create a VM with `--external-ip-attachment` and no network configuration; the VM is on the default Subnet with an automatic ExternalIP for inbound access
- [ ] Automatic ExternalIPs and ExternalIPAttachments appear in list views with the label `osac.openshift.io/auto-created`
- [ ] Deleting a VM with an automatic ExternalIP removes the automatic ExternalIP and ExternalIPAttachment
- [ ] Persistent automatic external cleanup failure leaves VM deletion pending with a diagnostic until repair, then resumes without losing address ownership
- [ ] After provisioning, VM status and the UI VM details list every interface with its name, Subnet, address, hardware address and primary flag
- [ ] Two VMs in one Subnet with different groups get their own stateful policies before traffic; a policy failure leaves the affected VM non-ready
- [ ] VMaaS creates a VM only after every interface's network is prepared, and the VM's first boot uses those networks
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
- Any physical network a network kind uses can be reached from the hosts that run VMs, and the provider's fabric serves addresses on it.
- The provider's management systems are reachable through the provider's fabric and can route back to the address range the provider reserves for management segments.
- VM images offered for more than one interface bring up every interface with DHCP; OSAC does not configure networking inside the guest. A provider that needs every VM manageable offers only such images.
- The management systems' addresses, the allowed ports, and the size and VLAN range of the management segments are set at installation and cannot be changed in this release.
- A tenant is one organization: VMs of one tenant are not protected from each other on networks without address enforcement (FR-8, FR-12).
- Every Subnet has the address range the service needs, because the provider's address plan covers every enabled service ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-plan)).

## 7. Dependencies

- **Unified Networking design** — the networking resource model ([Unified Networking design](/enhancements/OSAC-1433-unified-networking/design.md))
- **Default Networking PRD** — default Subnet and SecurityGroup selection ([Default Networking PRD](/enhancements/OSAC-1433-default-networking/prd.md))
- **Network Manager Integration Contract** — manager registration, task execution, and shared networking behavior that this PRD's VM behavior uses ([PRD](/enhancements/OSAC-1433-network-manager-integration-contract-networking/prd.md), [design](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md))
- **OSAC-1712 (automatic pool selection)** — the automatic ExternalIP pool choice ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access))
- **OSAC Kubernetes Managers** (`cudn_evpn` for the primary interface on the fabric overlay; `cudn_localnet` for VLAN networks as extra interfaces, including the management network) — see Risks 8.1 and 8.4.
- **OpenShift networking** support for extra VM interfaces on physical networks, and a provider fabric that delivers a tenant network to the VM hosts as a physical VLAN and serves its addresses, for the network kinds that need it.

## 8. Risks

### 8.1 Virtualization platform integration blocked or delayed

- **Owner:** Engineering / Product
- **Mitigation:** Without an OSAC Kubernetes Manager, VM creation is rejected; a Fabric Manager that lacks a network kind's technology makes only that network kind unavailable; the default network kind keeps working. When that kind is the management network, VMs are created without a management interface until it works.

### 8.2 Shared manager contract not implemented

- **Owner:** Platform team
- **Mitigation:** Deliver the shared manager registration, task execution, result validation, and recovery behavior before enabling provider-backed VM networking.

### 8.3 ExternalIPPool exhaustion

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** Pool capacity is visible in status; the error tells the tenant to contact the admin.

### 8.4 Fabric overlay networks cannot yet be extra interfaces

- **Owner:** OSAC networking team
- **Mitigation:** The fabric overlay kind serves only the primary interface until the platform supports it on extra interfaces; extra tenant interfaces use a kind that supports that position, and requests that break this fail at creation (FR-10, FR-11).

---

## Provenance

Committed: commit @ prd 0.11.5 - cd88680, workspace main @ 02d8d932a (42 behind origin/main)

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"cd88680","source_repo":"02d8d932a","source_repo_branch":"main","commits_behind_main":42,"commits_ahead_main":0,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
