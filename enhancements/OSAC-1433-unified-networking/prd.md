---
title: Unified Networking Requirements
authors:
  - dmanor@redhat.com
creation-date: 2026-06-03
last-updated: 2026-10-22
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
| Date        | 2026-10-22 |

## Contents

- [1. Problem Statement](#1-problem-statement)
- [2. Goals and Non-Goals](#2-goals-and-non-goals)
  - [2.1 Goals](#21-goals)
  - [2.2 Success Metrics](#22-success-metrics)
  - [2.3 Non-Goals](#23-non-goals)
  - [2.4 User Stories](#24-user-stories)
    - [Tenant Admin](#tenant-admin)
    - [Tenant User](#tenant-user)
    - [Cloud Infrastructure Admin](#cloud-infrastructure-admin)
    - [Cloud Provider Admin](#cloud-provider-admin)
- [3. Requirements](#3-requirements)
  - [3.1 Functional Requirements](#31-functional-requirements)
    - [FR-1: Network isolation and connectivity (R1)](#fr-1-network-isolation-and-connectivity-r1)
    - [FR-2: Infrastructure-agnostic networking resources (R2)](#fr-2-infrastructure-agnostic-networking-resources-r2)
    - [FR-3: Uniform networking across all service types (R3)](#fr-3-uniform-networking-across-all-service-types-r3)
    - [FR-4: ExternalIP is external to the VirtualNetwork (R4)](#fr-4-externalip-is-external-to-the-virtualnetwork-r4)
    - [FR-5: Clear ingress/egress separation (R5)](#fr-5-clear-ingressegress-separation-r5)
    - [FR-6: Modular networking backends with transparent selection (R6)](#fr-6-modular-networking-backends-with-transparent-selection-r6)
    - [FR-7: Single network attachment per workload (R7)](#fr-7-single-network-attachment-per-workload-r7)
    - [FR-8: Create/read/delete networking contract (R8)](#fr-8-createreaddelete-networking-contract-r8)
    - [FR-9: Strict resource lifecycle enforcement (R9)](#fr-9-strict-resource-lifecycle-enforcement-r9)
    - [FR-10: Provider networking control at installation](#fr-10-provider-networking-control-at-installation)
    - [FR-11: Unified networking UI and documentation](#fr-11-unified-networking-ui-and-documentation)
  - [3.2 Non-Functional Requirements](#32-non-functional-requirements)
- [4. Dependencies](#4-dependencies)
- [5. Support Boundaries](#5-support-boundaries)
  - [Deployment support boundary](#deployment-support-boundary)
  - [Networking hub support boundary](#networking-hub-support-boundary)

## 1. Problem Statement

OSAC tenants use several workload services and infrastructures, but networking has no consistent tenant-facing model across them. Tenant Admins and Tenant Users cannot apply one network model to every workload, and Cloud Infrastructure Admins must support several provider networking paths. A shared model gives tenants consistent control and gives providers one configurable networking contract.

## 2. Goals and Non-Goals

### 2.1 Goals

- Tenant Admins and Tenant Users use the same networking resources and workflows with every workload service that integrates the shared model.
- Tenants can isolate workloads, connect workloads on their networks, and control inbound and outbound external access.
- Cloud Infrastructure Admins choose the provider networking implementation; tenants need not understand or select it.
- Cloud Provider Admins choose at installation whether provider networking is enabled ([FR-10](#fr-10-provider-networking-control-at-installation)).
- Tenant Admins and Tenant Users manage the shared model through the unified UI and the supported API and CLI.

### 2.2 Success Metrics

| Metric | Target | Baseline |
|--------|--------|----------|
| Supported workload integrations using the shared networking model | 100% of services claiming unified networking support | Measured per deployment |
| Tenant-facing networking models required by those integrations | One shared model | Multiple service-specific models |

### 2.3 Non-Goals

- IPv6 or dual-stack networking.
- More than one network attachment per workload.
- VirtualNetwork peering or other cross-VirtualNetwork connectivity.
- Tenant-managed DNS zones, load balancers, or Internet gateways.
- Advanced interface configuration such as NIC bonding or VLAN trunking.
- Quota enforcement for networking resources.
- Tenant-facing FabricDomain API behavior and lifecycle, owned by Multi-Fabric East-West Networking (OSAC-1382).
- Enabling BMaaS or CaaS on a deployment that already has networking resources.

### 2.4 User Stories

#### Tenant Admin

- As a Tenant Admin, I want to create isolated VirtualNetworks and Subnets for workloads of every supported service, so that the network layout is the same across workload types.
- As a Tenant Admin, I want to define SecurityGroups and manage networking resources in the unified UI, so that I can govern my tenant's traffic and resource lifecycle.
- As a Tenant Admin, I want clear errors when a resource is not ready or still has dependents, so that I can fix a request without leaving resources stuck or breaking a workload.

#### Tenant User

- As a Tenant User, I want to attach a workload to a ready Subnet and SecurityGroups, so that I use the tenant's shared networking without choosing a provider implementation.
- As a Tenant User, I want an ExternalIP for inbound access or a NATGateway for outbound access, so that I get the access direction I need.
- As a Tenant User, I want the unified UI to show resource relationships and whether external access is available, so that I manage networking for all supported workload services in one place.

#### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to choose a provider networking service that meets OSAC's requirements and manage shared external address capacity, so that the provider can change implementations without changing the tenant resource model.
- As a Cloud Infrastructure Admin, I want to view the NetworkClass and ExternalIPPools in the unified UI, so that I can inspect the configured managers, east-west support, and address capacity.
- As a Cloud Infrastructure Admin, I want to set how each Subnet's addresses are split among VMs, the provider fabric, and cluster ingress addresses, so that Subnets have room for the services I run.

#### Cloud Provider Admin

- As a Cloud Provider Admin, I want to install OSAC with provider networking disabled while workloads use their documented fallback, so that I can run OSAC without provider network configuration.

## 3. Requirements

### 3.1 Functional Requirements

#### FR-1: Network isolation and connectivity (R1)

Tenants can create isolated VirtualNetworks. Workloads on one Subnet share a local network segment and communicate directly; workloads on different Subnets of one VirtualNetwork communicate through routing; both only when their SecurityGroups permit the traffic. A new connection between two workloads needs both the sender's egress rules and the receiver's ingress rules to permit it; established replies are allowed automatically. For traffic with only one OSAC workload endpoint, that workload's egress rules govern outbound and its ingress rules inbound. Workloads in separate VirtualNetworks stay isolated. This holds for every workload service that integrates the shared model.

Every workload interface on a Subnet gets its tenant IPv4 address by Dynamic Host Configuration Protocol (DHCP), and the workload service shows it in its normal status; tenants never set a static tenant-interface address. OSAC rejects, with a clear error, a Subnet whose range is too small for the deployment's address layout.

The Cloud Infrastructure Admin can set, at installation (a Helm upgrade may change it only while no networks exist), how each Subnet's addresses are split among VMs, the provider fabric (bare-metal servers, cluster workers, and provider devices), and cluster ingress addresses. Without a setting, OSAC chooses a split that fits the enabled services. OSAC rejects an invalid split at installation.

Every enforcement point that tenant traffic crosses, such as a VM's network policy or a bare-metal server's physical switch port, applies the shared SecurityGroup rules before the workload is reported network-ready. The Fabric Manager may leave the binding of VM addresses as a documented no-op, because each VM's network policy sees all of its traffic.

Separate VirtualNetworks, also of different tenants, may use identical or overlapping private IPv4 ranges. Providers keep routing, policy, allocation, and cleanup isolated by the owning VirtualNetwork, without globally unique private CIDRs or addresses. Sibling Subnets of one VirtualNetwork do not overlap, and independently owned endpoints on one Subnet get distinct addresses. OSAC rejects a VirtualNetwork whose range overlaps a range the provider reserves for its infrastructure (installation setting `global.networking.excludedIpv4Cidrs`) or an ExternalIPPool.

#### FR-2: Infrastructure-agnostic networking resources (R2)

Every networking resource keeps the same meaning across supported workload services and infrastructure. Workload-specific connection details need no separate networking resource model.

#### FR-3: Uniform networking across all service types (R3)

Tenant Admins and Tenant Users can use the shared VirtualNetwork, Subnet, SecurityGroup, ExternalIP, ExternalIPAttachment, and NATGateway resources with each integrating workload service. Provider-managed address pools supply ExternalIPs to those workloads.

#### FR-4: ExternalIP is external to the VirtualNetwork (R4)

An ExternalIP is an address outside the tenant's VirtualNetwork. The provider decides where it is reachable; OSAC does not promise reachability from the public Internet.

#### FR-5: Clear ingress/egress separation (R5)

An ExternalIPAttachment gives a workload inbound access; an optional NATGateway gives outbound access. They serve different purposes, and basic connectivity needs no NATGateway unless the workload service design requires one (CaaS needs one to bootstrap a Cluster).

#### FR-6: Modular networking backends with transparent selection (R6)

Cloud Infrastructure Admins can use any provider Fabric Manager that fulfills the OSAC manager contract and, to run VMs, an OSAC Kubernetes Manager whose network type that Fabric Manager supports. Resources keep their meaning across conforming managers and backend technologies; tenants do not select or need to understand the provider choice. The published test suite, not registration alone, demonstrates conformance. A deployment has exactly one NetworkClass; every VirtualNetwork and ExternalIPPool uses its managers, recorded at creation.

#### FR-7: Single network attachment per workload (R7)

Each workload has at most one network attachment. A workload service design defines any workload-specific interface selection.

#### FR-8: Create/read/delete networking contract (R8)

Tenant Admins and Tenant Users can create, list, view, and delete tenant networking resources within their tenant. Cloud Infrastructure Admins can create, list, view, and delete ExternalIPPools; they set the one NetworkClass through installation values, can view it, and delete it only to replace it. Access follows ownership and authorization.

No networking resource changes in place, with one exception: a tenant can replace a SecurityGroup's complete ingress and egress rules, and OSAC applies them to every workload that uses the group. When a rule update fails, each manager keeps the rules of its last successful run, and the SecurityGroup shows the failure ([design](design.md#api-operation-constraint)). Any other change means replacing the resource. A workload's network attachment is fixed at workload creation and changes only by replacing the workload.

#### FR-9: Strict resource lifecycle enforcement (R9)

OSAC rejects creating a networking resource or workload before its referenced resources complete their required lifecycle, and deleting a resource that active resources depend on, also when requests arrive at the same time. It explains the unmet prerequisite or blocking resource so users can correct the request. OSAC retries transient provider failures automatically. When provider work fails in a way retrying cannot fix, the resource stays not ready with a clear message, and the user deletes it.

#### FR-10: Provider networking control at installation

A Cloud Provider Admin chooses at installation, through Helm or the Enclave Wizard, whether OSAC provider networking is enabled. The setting defaults to enabled and cannot change after installation: a rollout that changes it fails, and changing it needs a reinstall. Networking APIs stay available through the supported API, CLI, and UI, with their normal authorization, validation, defaults, and dependency rules.

When provider networking is disabled, OSAC still manages networking objects but does not apply provider network configuration, allocate provider addresses, or clean up provider networking. Object status promises no network connectivity or provider-side change. Workload provisioning stays available when its other prerequisites are met, with the fallback each workload service design defines. OSAC provides no tenant network connectivity, ExternalIP allocation, or outbound NAT, and rejects ExternalIP creates with a clear error.

#### FR-11: Unified networking UI and documentation

Tenant Admins and Tenant Users can manage VirtualNetworks, Subnets, SecurityGroups, ExternalIPs, ExternalIPAttachments, and NATGateways in the unified UI, and use shared resource pickers in integrating workload services. Cloud Infrastructure Admins can inspect the provider NetworkClass and ExternalIPPools. User documentation explains the resource workflows (creation, SecurityGroup rule update, and deletion), workload network attachments, ExternalIP reachability, and provider networking control.

### 3.2 Non-Functional Requirements

None.

## 4. Dependencies

- **Unified Networking Design:** the [design](design.md) defines the technical approach.
- **Default Networking:** the [Default Networking Design](/enhancements/OSAC-1433-default-networking/design.md) defines tenant default resources.
- **Workload service designs:** each integrating service documents its workload API mapping, readiness gates, status flow, and cleanup on the shared model.
- **Network Manager Integration Contract:** its [PRD](/enhancements/OSAC-1433-network-manager-integration-contract-networking/prd.md) defines the contract and conformance. Providers write the Fabric Manager and OSAC writes the Kubernetes Managers; OSAC rejects a Kubernetes Manager whose network type the Fabric Manager does not support.
- **Multi-Fabric East-West Networking (OSAC-1382):** its [design](/enhancements/OSAC-1382-multi-fabric-east-west-networking/design.md) defines tenant-facing FabricDomain behavior; this proposal defines how FabricDomain relates to VirtualNetworks and how the NetworkClass gates the optional capability.
- **Unified Networking UI (OSAC-2226):** tracks the standalone networking UI, its screen-level UX, and the shared resource pickers FR-11 requires.
- **User documentation:** API, CLI, and UI guidance reflects the shared resource lifecycle and this PRD's support limits.
- **Three-Layer Networking Model:** [architecture reference](https://docs.google.com/document/d/1MwBjpmYoZoUN3PVjeIRZ2Y6mBuf0lu1uvTtN6XXPPTM).

## 5. Support Boundaries

### Deployment support boundary

Networking supports connected deployments only: the provider-owned hub, the selected networking services, and the provider's address infrastructure reach each other within the deployment. Every deployment uses a provider Fabric Manager; running VMs also needs an OSAC Kubernetes Manager. Details: [design](design.md#deployment-support-boundary).

### Networking hub support boundary

Networking supports one hub: the management cluster where the OSAC operator, the OSAC resources, AAP, and VMs run. VMs in a separate cluster and coordination across clusters are not supported. Details: [design](design.md#networking-hub-support-boundary).

---

## Provenance

Authored: revise @ prd 0.11.5 - a58bdf7, workspace docs/unified-networking-docs-structure @ 64da781
Phases: manual-edit, revise

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"a58bdf7","source_repo":"64da781","source_repo_branch":"docs/unified-networking-docs-structure","commits_behind_main":0,"commits_ahead_main":60,"main_ref":"main","phases":["manual-edit","revise"],"authoring_modes":["manual","skill"],"context_changed":false,"origin_untracked":true} -->
