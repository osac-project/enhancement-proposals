---
title: Unified Networking Requirements
authors:
  - dmanor@redhat.com
creation-date: 2026-06-03
last-updated: 2026-10-13
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1433
see-also:
  - Unified Networking Design: /enhancements/OSAC-1433-unified-networking
  - Network Manager Integration Contract PRD: /enhancements/OSAC-1433-network-manager-integration-contract-networking/prd.md
  - Network Manager Integration Contract Design: /enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md
  - Three-Layer Networking Model: https://docs.google.com/document/d/1MwBjpmYoZoUN3PVjeIRZ2Y6mBuf0lu1uvTtN6XXPPTM
replaces:
  - N/A
superseded-by:
  - N/A
---

# Unified Networking Requirements

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1433 |
| Target release | OSAC 0.2 |
| Date        | 2026-10-06 |

## Contents

- [Problem Statement](#1-problem-statement)
- [Goals and Non-Goals](#2-goals-and-non-goals)
  - [Goals](#21-goals)
  - [Success Metrics](#22-success-metrics)
  - [Non-Goals](#23-non-goals)
- [User Stories](#user-stories)
  - [Tenant Admin](#tenant-admin)
  - [Tenant User](#tenant-user)
  - [Cloud Infrastructure Admin](#cloud-infrastructure-admin)
  - [Cloud Provider Admin](#cloud-provider-admin)
- [Requirements](#3-requirements)
  - [Functional Requirements](#31-functional-requirements)
  - [Non-Functional Requirements](#32-non-functional-requirements)
- [Dependencies](#4-dependencies)
- [Support Boundaries](#support-boundaries)
  - [Deployment support boundary](#deployment-support-boundary)
  - [Networking hub support boundary](#networking-hub-support-boundary)

## 1. Problem Statement

OSAC tenants use different workload services and infrastructure, but networking does not have one consistent tenant-facing model across them. Tenant Admins and Tenant Users cannot apply the same network model to every supported workload, and Cloud Infrastructure Admins must support different provider networking paths. A shared networking model gives tenants consistent control and gives providers one configurable networking contract to support.

## 2. Goals and Non-Goals

### 2.1 Goals

- Tenant Admins and Tenant Users can use the same networking resources and workflows with every workload service that integrates the shared model.
- Tenants can isolate workloads, connect workloads on their networks, and control inbound and outbound external access.
- Cloud Infrastructure Admins choose the provider networking implementation without requiring tenants to understand or select it.
- Cloud Provider Admins can disable provider-network operations while integrating workload services use their documented fallback, then re-enable them through a coordinated maintenance transition that restores provider networking before new workloads are admitted.
- Tenant Admins and Tenant Users can manage the shared networking model through the unified UI and the supported API and CLI surfaces.

### 2.2 Success Metrics

| Metric | Target | Baseline |
|--------|--------|----------|
| Supported workload integrations using the shared networking model | 100% of services claiming unified networking support | Measured per deployment |
| Tenant-facing networking models required by those integrations | One shared model | Multiple service-specific models |

### 2.3 Non-Goals

- IPv6 or dual-stack networking.
- More than one tenant network attachment per workload.
- VirtualNetwork peering or other cross-VirtualNetwork connectivity.
- Tenant-managed DNS zones, load balancers, or Internet gateways.
- Advanced interface configuration such as NIC bonding or VLAN trunking.
- Quota enforcement for networking resources.

## User Stories

### Tenant Admin

- As a Tenant Admin, I want to create isolated VirtualNetworks and Subnets for workloads across supported services, so that the network layout is consistent across workload types.
- As a Tenant Admin, I want to define SecurityGroups and manage networking resources through the unified UI, so that I can govern traffic and resource lifecycle for my tenant.
- As a Tenant Admin, I want clear errors when a resource is not ready or still has dependents, so that I can correct a request without leaving resources stuck or breaking a workload.

### Tenant User

- As a Tenant User, I want to attach a workload to a ready Subnet and SecurityGroups, so that I can use the tenant's shared networking without choosing a provider implementation.
- As a Tenant User, I want to request an ExternalIP for inbound access or a NATGateway for outbound access, so that I can use the access direction I need.
- As a Tenant User, I want the unified UI to show resource relationships and whether external access is available, so that I can manage networking across supported workload services in one place.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to choose a provider networking service that meets OSAC's requirements and manage shared external address capacity, so that the provider can change implementations without changing the tenant resource model.
- As a Cloud Infrastructure Admin, I want to view NetworkClasses and ExternalIP pools in the unified UI, so that I can inspect configured manager roles, east-west support, and address capacity.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to disable provider networking while workloads use their documented fallback, then re-enable it after a coordinated maintenance transition, so that workloads return to provider-managed networking only after it is ready.

The unified UI is in scope as a product outcome and is tracked by [OSAC-2226](https://redhat.atlassian.net/browse/OSAC-2226). This PRD defines resource and workflow outcomes; screen-level UX is covered by that UI work. User documentation must explain resource creation and deletion, workload attachment, ExternalIP reachability, and disabled-provider behavior.

The target release is OSAC 0.2. The provider networking setting is included because it defines the operating mode for the shared resources across supported workload services, including behavior when provider networking is disabled.

## 3. Requirements

### 3.1 Functional Requirements

#### FR-1: Network isolation and connectivity (R1)

Tenants must be able to create isolated VirtualNetworks. Workloads on the same
Subnet share a local network segment and can communicate directly when their
attached SecurityGroups permit the traffic. Workloads on different Subnets in
the same VirtualNetwork can communicate through routing when their
SecurityGroups permit the traffic. For a new connection between two
workloads, both the sender's egress rules and the receiver's ingress rules
must permit it; established replies are allowed automatically. For traffic
with only one OSAC workload endpoint, outbound access uses that workload's
egress rules and inbound access uses its ingress rules. Workloads in separate
VirtualNetworks remain isolated. These outcomes apply to every workload
service that integrates the shared networking model. [User]

Every workload interface attached to a Subnet obtains its tenant IPv4 address through Dynamic Host Configuration Protocol (DHCP). The workload service exposes the assigned address through its normal status; tenants do not provide a static tenant-interface address. [User]

Tenants may choose identical or overlapping private IPv4 ranges for separate isolated VirtualNetworks, including networks belonging to different tenants. Providers preserve routing, policy, allocation, and cleanup isolation using the owning VirtualNetwork context, without requiring globally unique private CIDRs or addresses. Sibling Subnets within one VirtualNetwork do not overlap, and independently owned endpoints within one shared Subnet receive distinct addresses. [User]

#### FR-2: Infrastructure-agnostic networking resources (R2)

Every networking resource retains the same meaning across supported workload services and infrastructure. Workload-specific connection details do not require a separate networking resource model.

#### FR-3: Uniform networking across all service types (R3)

Tenant Admins and Tenant Users can use the shared VirtualNetwork, Subnet, SecurityGroup, ExternalIP, ExternalIPAttachment, and NATGateway resources with each integrating workload service. Provider-managed address pools make ExternalIPs available to those workloads.

#### FR-4: ExternalIP is external to the VirtualNetwork (R4)

An ExternalIP provides an address outside a tenant's VirtualNetwork. The provider determines where that address is reachable; OSAC does not promise that it is reachable from the public Internet.

#### FR-5: Clear ingress/egress separation (R5)

Tenants can configure inbound access to a workload with an ExternalIPAttachment and optional outbound access with a NATGateway. ExternalIPAttachment and NATGateway serve different purposes, and a NATGateway is not required for a workload to have basic connectivity.

#### FR-6: Modular networking backends with transparent selection (R6)

Cloud Infrastructure Admins can use any Fabric Manager and, where needed, any Kubernetes Manager that fulfills its OSAC role contract. The same resources retain their meaning across conforming manager implementations and backend technologies; tenants do not select or need to understand the provider choice.

#### FR-7: Single network attachment per workload (R7)

Each workload can use at most one tenant network attachment. A service extension defines any workload-specific interface selection. Multiple tenant attachments per workload are outside this proposal's scope.

#### FR-8: Create/read/delete networking contract (R8)

Tenant Admins and Tenant Users can create, list, view, and delete tenant-managed networking resources within their tenant. Cloud Infrastructure Admins can create, list, view, and delete provider-managed NetworkClasses and ExternalIP pools according to their role. Resource access follows ownership and authorization. No networking resource can be changed in place; a change requires replacing it. A workload's network attachment is also fixed when the workload is created and can be changed only by replacing the workload.

#### FR-9: Strict resource lifecycle enforcement (R9)

OSAC prevents users from creating a networking resource or workload before its referenced resources complete their required lifecycle, and prevents deletion of a resource that active resources depend on. OSAC returns a clear explanation of the unmet prerequisite or blocking resource so users can correct the request.

#### FR-10: Provider networking control at installation or upgrade

A Cloud Provider Admin can enable or disable OSAC provider networking through Helm or the Enclave Wizard during installation or upgrade. The setting defaults to enabled and takes effect after the rollout. Networking APIs remain available through supported API, CLI, and UI surfaces, and retain their normal authorization, validation, defaults, and dependency rules.

When disabled, OSAC continues to manage networking objects but does not apply provider network configuration, allocate provider addresses, or clean up provider networking. Logical object status does not promise network connectivity or provider-side changes; existing provider rules or resources may remain until the provider cleans them up. Ordinary workload provisioning remains available when its other prerequisites are met, with the service-specific fallback defined by each workload extension. Tenant network connectivity, ExternalIP allocation, and outbound NAT are not provided by OSAC in this mode. [User]

Re-enabling provider networking after disabled operation is a coordinated maintenance transition. Workload owners delete existing workloads through their service's normal lifecycle, and the Cloud Provider Admin reconciles provider-side leftovers before workloads return to provider-managed networking. OSAC reports blockers, temporarily rejects new workload creation requests, and keeps workload reads/deletes and networking-resource cleanup available. It does not automatically stop, delete, or migrate running workloads. OSAC allows new workloads again only after accepted work is resolved and provider networking is ready; each workload still requires its own ready network references. [User]

#### FR-11: Unified networking UI and documentation

Tenant Admins and Tenant Users can manage VirtualNetworks, Subnets, SecurityGroups, ExternalIPs, ExternalIPAttachments, and NATGateways through the unified UI, and can use shared resource pickers from integrating workload services. Cloud Infrastructure Admins can inspect provider NetworkClasses and ExternalIP pools. User documentation explains the supported resource workflows, workload attachments, ExternalIP reachability, and provider networking control.

### 3.2 Non-Functional Requirements

No non-functional requirements were specified for this proposal.

## 4. Dependencies

- **Unified Networking Design:** [/enhancements/OSAC-1433-unified-networking](/enhancements/OSAC-1433-unified-networking) defines the technical approach for these requirements.
- **Default Networking:** [/enhancements/OSAC-1433-default-networking](/enhancements/OSAC-1433-default-networking) defines tenant default-resource automation.
- **Workload service extensions:** Each integrating service documents its workload API mapping, readiness gates, status flow, and cleanup using the shared networking model.
- **Network Manager Integration Contract:** Its [PRD](/enhancements/OSAC-1433-network-manager-integration-contract-networking/prd.md) defines how providers add networking implementations that work together while preserving the shared tenant networking model.
- **Unified Networking UI (OSAC-2226):** Tracks the standalone networking UI and shared resource pickers required by FR-11.
- **User documentation:** API, CLI, and UI guidance must reflect the shared resource lifecycle and the support limits in this PRD.
- **Three-Layer Networking Model:** [Architecture reference](https://docs.google.com/document/d/1MwBjpmYoZoUN3PVjeIRZ2Y6mBuf0lu1uvTtN6XXPPTM).

## Support Boundaries

### Deployment support boundary

Networking supports connected deployments only. The provider-owned hub,
selected networking services, and provider-controlled address infrastructure
must be reachable within that deployment.

### Networking hub support boundary

Each deployment has one provider-owned networking hub. Multiple hosting
clusters remain supported where a workload feature calls for them, but
networking resources are not coordinated across multiple hubs.

---

## Provenance

Authored: revise @ prd 0.11.3 - 2bd6607, workspace main @ 1f3b63b82 (58 behind origin/main)
Final: revise @ prd 0.11.5 - 1c6e8de, workspace main @ 97d046f86 (16 behind origin/main)

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"97d046f86","source_repo_branch":"main","commits_behind_main":16,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","manual-edit","revise","manual-edit","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
