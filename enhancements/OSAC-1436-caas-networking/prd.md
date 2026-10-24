---
title: caas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-10-22
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1436
see-also:
  - Unified Networking PRD: /enhancements/OSAC-1433-unified-networking/prd.md
  - CaaS Networking Design: /enhancements/OSAC-1436-caas-networking/design.md
replaces:
  - N/A
superseded-by:
  - N/A
---

# CaaS Networking — Unified API with Automatic External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1436 |
| Date        | 2026-10-22 |

This PRD extends the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md) for clusters and inherits its [deployment](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary) and [hub](/enhancements/OSAC-1433-unified-networking/design.md#networking-hub-support-boundary) support boundaries and [create/read/delete contract, with its SecurityGroup rule update](/enhancements/OSAC-1433-unified-networking/prd.md#fr-8-createreaddelete-networking-contract-r8).

Connectivity, allocation, and cleanup described here apply with provider networking enabled; FR-12 covers provider networking disabled. Validation, default SecurityGroup selection, immutability, and dependency rules apply in both cases.

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
    - [Endpoint Discovery](#endpoint-discovery)
    - [External IP Activation](#external-ip-activation)
    - [Host Selection and Network Configuration](#host-selection-and-network-configuration)
    - [Network Connectivity Setup](#network-connectivity-setup)
    - [Public DNS Names](#public-dns-names)
    - [Worker Interface Availability](#worker-interface-availability)
    - [Bare-Metal Only](#bare-metal-only)
    - [Automatic Resource Cleanup](#automatic-resource-cleanup)
    - [Provider Networking Disabled](#provider-networking-disabled)
    - [Shared Network Behavior](#shared-network-behavior)
    - [Stateful Attachment Policy](#stateful-attachment-policy)
    - [Automatic Cluster SecurityGroup](#automatic-cluster-securitygroup)
    - [Worker Path to Management Endpoints](#worker-path-to-management-endpoints)
  - [4.2 Non-Functional Requirements](#42-non-functional-requirements)
- [5. Acceptance Criteria](#5-acceptance-criteria)
- [6. Assumptions](#6-assumptions)
- [7. Dependencies](#7-dependencies)
- [8. Risks](#8-risks)
  - [8.1 Suitable host availability](#81-suitable-host-availability)
  - [8.2 Endpoint discovery delay or failure](#82-endpoint-discovery-delay-or-failure)
  - [8.3 Suitable tenant interfaces are unavailable](#83-suitable-tenant-interfaces-are-unavailable)
  - [8.4 IP address pool configuration for API and ingress endpoints](#84-ip-address-pool-configuration-for-api-and-ingress-endpoints)

## 1. Problem Statement

Cluster provisioning has no networking configuration. Tenants cannot choose the Subnet for their cluster nodes, place two clusters in one VirtualNetwork, or isolate them in separate networks. All clusters share one deployment-wide networking backend, and cluster networking differs from the VM and bare-metal server workflows.

## 2. Goals and Non-Goals

### 2.1 Goals

- A Cluster has one network attachment, explicit (Subnet and SecurityGroups) or from the tenant's defaults; its one Subnet serves all node sets, and the service chooses a suitable interface for each node set
- Every cluster gets ExternalIPs and public DNS names for its API server and ingress endpoints, without pre-creating ExternalIP resources
- Cluster status exposes the API server and ingress endpoint addresses
- Cluster creation provisions suitable bare-metal hosts and their network connectivity
- Cluster deletion cleans up its automatic ExternalIPs and ExternalIPAttachments
- Administrators can make suitable tenant-facing interfaces discoverable for each server type

### 2.2 Non-Goals

- VM-based cluster node sets
- A tenant DNS API; CaaS publishes only its own endpoint records
- Enabling clusters on a deployment that already has networking resources ([Unified — Subnet address plan](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-plan))

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a cluster on a specific Subnet with specific SecurityGroups
- As a Tenant User, I want node sets to use a suitable tenant-facing interface automatically, so that I need not know the host's port layout
- As a Tenant User, I want every cluster to get ExternalIPs and public names for its API server and ingress, so that it is reachable from outside without extra resources or flags
- As a Tenant User, I want a cluster created without network configuration to use my default Subnet and SecurityGroups
- As a Tenant User, I want to see my cluster's API server and ingress endpoint addresses in its status, so that I can access it
- As a Tenant User, I want automatic networking resources cleaned up when I delete my cluster, so that none are orphaned

### Tenant Admin Stories

- As a Tenant Admin, I want to place several clusters in one VirtualNetwork, so that they communicate privately with each other and with my VMs
- As a Tenant Admin, I want to isolate clusters in separate VirtualNetworks, so that I can enforce boundaries between projects or teams

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to make suitable tenant-facing interfaces discoverable for cluster node types, so that the service can connect them to the selected Subnet

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want to see whether Cluster networking is ready and what failed, so that I can troubleshoot provisioning

## 4. Requirements

### 4.1 Functional Requirements

#### Network Attachment

- **FR-1:** A tenant can attach a Cluster to one Subnet, shared by all of its node sets, with SecurityGroups of that Subnet's VirtualNetwork. The selection is fixed at Cluster creation. The service chooses a suitable tenant-facing interface for each node set.

#### Optional Network Attachment with Defaults

- **FR-2:** Network selection is optional; an omitted or partial selection is resolved as [Default Networking PRD FR-6](/enhancements/OSAC-1433-default-networking/prd.md#optional-network-attachment-with-defaults) defines.

#### Automatic External Access

- **FR-3:** Every Cluster gets automatic external access ([Default Networking PRD FR-8](/enhancements/OSAC-1433-default-networking/prd.md#automatic-external-access)) for its management API and guest ingress endpoints; a tenant cannot turn it off.

#### Endpoint Discovery

- **FR-4:** Cluster status makes the API and guest ingress addresses available when they are known, and the API and console URLs, which use the public names, once the Cluster is ready. The Cluster's external addresses are reported on their own resources.

#### External IP Activation

- **FR-5:** OSAC activates each inbound route only after its external address is real and the matching API or ingress endpoint address is known; it does not wait for the Cluster to be ready. The Cluster reports ready only after both routes are active and its public names are published.

#### Host Selection and Network Configuration

- **FR-6:** Cluster creation uses available hosts that meet each node set's selected type. Worker installation can proceed once required management connectivity is available.

#### Network Connectivity Setup

- **FR-7:** Each worker joins the selected tenant network with the requested SecurityGroup policy and gets a tenant address before joining the Cluster. A network or address-discovery failure is visible on the Cluster, the worker is not reported as connected, and it is handled like any other failed worker.

#### Public DNS Names

- **FR-8:** The Cluster's API and ingress names have one public record set that points to its external addresses. Users outside the Cluster, and the Cluster itself, resolve the names through these records, and the names match the Cluster's certificates.

#### Worker Interface Availability

- **FR-9:** Tenants and administrators can discover the available network interfaces and their relevant characteristics for each bare-metal instance type.

#### Bare-Metal Only

- **FR-10:** Cluster node sets are bare metal; VM-based node sets are a [non-goal](#22-non-goals).

#### Automatic Resource Cleanup

- **FR-11:** Automatically created external addresses and routes are visible and identifiable to their owner. Cluster deletion removes them and the Cluster's dependent network state in a safe order. If provider cleanup fails, deletion stays pending with a diagnostic until cleanup can continue. The owner removes manually created inbound routes first; shared tenant defaults remain.

#### Provider Networking Disabled

- **FR-12:** A Cloud Provider Admin can install a deployment with provider networking disabled ([Unified PRD FR-10](/enhancements/OSAC-1433-unified-networking/prd.md#fr-10-provider-networking-control-at-installation)); Cluster provisioning and deletion stay available on baseline connectivity. With provider networking disabled, OSAC configures no tenant network, ExternalIP route, or DNS record, and a Cluster never accepts an ExternalIPAttachment. The provider makes the Cluster's API, application names, and ingress reachable outside OSAC. Endpoint addresses appear only when the baseline supplies them. Status shows that provider work is not done.

#### Shared Network Behavior

- **FR-13:** CaaS works in a deployment without VM networking. Clusters stay isolated when tenants use identical private CIDRs, and guest endpoints sharing a Subnet get distinct addresses that do not collide with workload addresses.

#### Stateful Attachment Policy

- **FR-14:** Each worker interface applies the stateful policy ([Unified PRD FR-1](/enhancements/OSAC-1433-unified-networking/prd.md#fr-1-network-isolation-and-connectivity-r1)) of its selected SecurityGroups combined with the Cluster's automatic SecurityGroup (FR-15); unmatched new traffic is denied. Policy is active before traffic, and connectivity is reported only after attachment readiness. A policy failure is visible and keeps the dependent network step non-ready.

#### Automatic Cluster SecurityGroup

- **FR-15:** Every Cluster gets one automatic SecurityGroup in its VirtualNetwork, with provider networking enabled or disabled. It allows all traffic from the Cluster's Subnet, inbound TCP 80 and 443 from anywhere, and all outbound traffic, and applies to every worker in addition to the selected SecurityGroups, so a Cluster works with any tenant SecurityGroups, including minimal defaults. Tenants can see it but cannot delete it or select it for anything else. OSAC removes it after the Cluster's last worker is gone. Because rules use address ranges only, other workloads on the same Subnet can also reach the workers.

#### Worker Path to Management Endpoints

- **FR-16:** With provider networking enabled, workers reach the platform's management endpoints for installation through the NATGateway of the Cluster's VirtualNetwork, and OSAC rejects a Cluster whose VirtualNetwork has no READY NATGateway. OSAC rejects deleting that NATGateway while a Cluster uses its VirtualNetwork. The provider supplies DNS and the route from that NATGateway's address to the management endpoints, and the network carries traffic from that NATGateway to the Cluster's own external addresses.

### 4.2 Non-Functional Requirements

- **NFR-1:** OSAC checks external address capacity before accepting a Cluster. Address assignment and endpoint discovery may continue asynchronously, without a circular wait between external access and Cluster readiness.

## 5. Acceptance Criteria

- [ ] A cluster whose external address assignment is delayed stays in progress and becomes ready once both external routes are active and its public names resolve
- [ ] Two tenants with identical private Subnet CIDRs each get a cluster with isolated ingress; concurrent clusters on one Subnet get distinct ingress addresses
- [ ] A cluster-only deployment without VM networking provisions API and guest ingress correctly
- [ ] The API and ingress external addresses reach the management-hosted API and the tenant-hosted router, and the cluster's public names resolve to them from outside and inside the cluster
- [ ] With provider networking enabled, a persistent cleanup failure leaves deletion pending with a diagnostic and keeps address ownership until repair
- [ ] A cluster created with a Subnet and SecurityGroups has its nodes on that Subnet
- [ ] A cluster with several node sets uses one tenant Subnet, and the service selects a suitable interface for each node set
- [ ] A cluster created without network configuration uses the default Subnet and gets automatic ExternalIPs for API and ingress; a request that turns automatic external access off is rejected
- [ ] Cluster status exposes the API server and ingress endpoint addresses
- [ ] Each inbound route becomes available only after its external address is real and the matching endpoint address is known
- [ ] Automatic ExternalIPs and ExternalIPAttachments carry the `osac.openshift.io/auto-created` label, are visible in list views, and are removed when the cluster is deleted
- [ ] A cluster whose tenant default SecurityGroups allow only SSH and HTTPS installs; its workers reach each other, DNS, and the management endpoints, and its ingress answers on ports 80 and 443
- [ ] The automatic Cluster SecurityGroup is visible to the tenant, cannot be deleted or selected by the tenant, and is removed when the cluster is deleted
- [ ] With provider networking disabled and sufficient baseline connectivity, cluster installation and deletion work; OSAC promises no tenant-managed address or route
- [ ] With provider networking disabled, CaaS reports endpoint addresses only when the baseline supplies them and never presents an unassigned tenant address as reachable
- [ ] With provider networking disabled, automatic external access does not block installation, exposes no fabricated address or route, and never gives that cluster external access
- [ ] Default SecurityGroup resolution, invalid-reference and non-ready-dependency rejection, tenant boundaries, and interface, cardinality, and immutability rules stay active
- [ ] With provider networking disabled, deletion runs no provider cleanup and never claims a tenant network interface was restored
- [ ] Update rules meet [Unified PRD FR-8](/enhancements/OSAC-1433-unified-networking/prd.md#fr-8-createreaddelete-networking-contract-r8) for Clusters

## 6. Assumptions

- The tenant has default networking resources (VirtualNetwork, Subnet, SecurityGroup, and, with provider networking enabled, NATGateway). Without them, creating a cluster without network configuration fails with a clear error.
- The NetworkClass selects a registered Fabric Manager with a conformant report from the conformance suite whose `cluster` profile passed.
- Every Subnet has the address range the service needs, because the provider's address plan covers every enabled service ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-plan)).
- Each offered bare-metal server type exposes a suitable tenant-facing interface.

## 7. Dependencies

- **[Unified Networking design](/enhancements/OSAC-1433-unified-networking/design.md)** — the networking resource model (VirtualNetworks, Subnets, SecurityGroups, ExternalIPs, ExternalIPAttachments, NATGateways)
- **[Default Networking PRD](/enhancements/OSAC-1433-default-networking/prd.md)** — default Subnet and SecurityGroup selection
- **Network Manager Integration Contract** ([PRD](/enhancements/OSAC-1433-network-manager-integration-contract-networking/prd.md), [design](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md)) — the Fabric Manager requirements and shared task execution that the cluster lifecycle uses

## 8. Risks

### 8.1 Suitable host availability

- **Owner:** Platform team
- **Mitigation:** The deployment provides enough bare-metal hosts of the required types; an actionable error reports when none is available.

### 8.2 Endpoint discovery delay or failure

- **Owner:** Platform team
- **Mitigation:** Undiscovered endpoint addresses do not appear in cluster status, their ExternalIPAttachments do not activate, and the cluster does not become ready. Cluster status names the unfinished or failed endpoint step, so an administrator can repair it.

### 8.3 Suitable tenant interfaces are unavailable

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** Each server type offered for cluster nodes has at least one tenant-facing interface. A cluster create, or a node set added later, whose server type has none is rejected with a clear error, so no node joins without tenant connectivity.

### 8.4 IP address pool configuration for API and ingress endpoints

- **Owner:** Platform team / Cloud Infrastructure Admin
- **Mitigation:** The management API path is available for worker installation, and guest ingress addresses stay unique among clusters that share a Subnet. Address ownership is kept until cleanup completes.

---

## Provenance

Authored: revise @ prd 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)
Final: manual-edit [manual] @ prd 0.11.5 - 0c7ea35, workspace main @ 14c4d6f1c (17 behind origin/main)

> Context changed between revise and manual-edit.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"0c7ea35","source_repo":"14c4d6f1c","source_repo_branch":"main","commits_behind_main":17,"commits_ahead_main":0,"main_ref":"main","phases":["revise","manual-edit","revise","manual-edit","revise","manual-edit","revise","respond","revise","manual-edit"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
