---
title: Unified Networking Requirements for VMaaS, CaaS, and BMaaS
authors:
  - dmanor@redhat.com
creation-date: 2026-06-03
last-updated: 2026-09-24
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1433
see-also:
  - Unified Networking Design: /enhancements/OSAC-1433-unified-networking
  - BareMetal Instance API: /enhancements/OSAC-1118-baremetal-instance-api
replaces:
  - N/A
superseded-by:
  - N/A
---

# Unified Networking Requirements for VMaaS, CaaS, and BMaaS

| Field       | Value                                      |
|-------------|--------------------------------------------|
| Author(s)   | Dan Manor (dmanor@redhat.com)              |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1433 |
| Date        | 2026-09-24                                 |

## 1. Problem Statement

VMaaS, CaaS, and BMaaS need one networking model so tenants can connect workloads across service types without learning deployment-specific networking implementations. Today, service teams use separate workflows, and workload-level traffic policies do not provide a consistent subnet-wide boundary. This leaves tenants without a shared way to define and inspect network placement and traffic access.

## 2. Goals and Non-Goals

### 2.1 Goals

- Tenants use the same VirtualNetwork, Subnet, NetworkACL, and external-access resources across VMaaS, CaaS, and BMaaS.
- Tenants control ingress and egress traffic for all workloads on a Subnet through ordered, stateless NetworkACL rules.
- Workloads in the three services can share a VirtualNetwork and Subnet while retaining at most one tenant network attachment per workload.
- Providers select and operate networking implementations without exposing those implementation choices to tenants.
- Tenants use provider-routable IPv4 addressing in connected deployments.

### 2.2 Success Metrics

| Metric | Target | Baseline |
|--------|--------|----------|
| Service types using the networking API | 3/3 (VMaaS, CaaS, BMaaS) | 1/3 (VMaaS only) |
| Service types bypassing the networking API for network configuration | 0/3 | 2/3 (CaaS, BMaaS) |
| API changes required to add a networking implementation | 0 | Requires API and operator changes |

### 2.3 Non-Goals

- VPC peering or communication between VirtualNetworks
- Tenant-managed DNS zones
- Load balancer or Internet Gateway APIs
- IPv6 and dual-stack networking
- Multi-hub networking placement or cross-hub connectivity
- Multiple tenant network attachments per workload
- Quota enforcement for networking resources
- Per-physical-interface configuration beyond selecting one BMaaS interface

## 3. Requirements

### 3.1 Functional Requirements

- **FR-1:** Tenants can create isolated VirtualNetworks and Subnets. Resources in different VirtualNetworks cannot communicate, and resources in the same Subnet share a broadcast domain. [Jira: OSAC-1433]
- **FR-2:** Tenants can create a NetworkACL within a VirtualNetwork and define separate ingress and egress rules. Each rule specifies whether matching traffic is allowed or denied, a unique numeric priority from 1 through 32766 within its direction, protocol, an optional TCP or UDP destination-port range, and a canonical IPv4 CIDR. Lower priorities are evaluated first; the first matching rule decides, and traffic that matches no rule is denied. [User]
- **FR-3:** NetworkACLs are stateless. Ingress and egress are evaluated independently, and return traffic requires a matching rule in the reverse direction. [User]
- **FR-4:** A Subnet has exactly one associated NetworkACL. Tenants can reuse one NetworkACL on multiple Subnets in the same VirtualNetwork. The policy applies uniformly to every workload attached to that Subnet. Traffic between workloads on the same Subnet is not filtered by the Subnet's NetworkACL. For traffic between Subnets, source egress and destination ingress rules are evaluated independently. [User]
- **FR-5:** NetworkACL rules and a Subnet's NetworkACL association are fixed at creation. Changing them requires deleting and recreating the affected networking resources. A VirtualNetwork's and Subnet's address configuration and a workload's network attachment also remain fixed after creation. [User]
- **FR-6:** ComputeInstance, Cluster, and BaremetalInstance attachments identify a Subnet and do not carry traffic-policy references. A BaremetalInstance attachment may also identify one physical interface. Each workload supports at most one tenant network attachment. [User; OSAC-1433]
- **FR-7:** The networking API provides read (list/get), create, and delete operations for networking resources. NetworkACL rules and Subnet-to-NetworkACL associations cannot be updated after creation. Workload attachments remain immutable after workload creation. [User; OSAC-1433]
- **FR-8:** All three service types use the same network resource model and can place workloads on any compatible Subnet. A Subnet and its associated NetworkACL belong to the same VirtualNetwork. [Jira: OSAC-1433]
- **FR-9:** Tenants can allocate ExternalIPs and attach them to ComputeInstances, Clusters, and BaremetalInstances for inbound traffic. ExternalIP means external to the VirtualNetwork and does not promise Internet reachability. [Jira: OSAC-1433]
- **FR-10:** A NATGateway can provide a stable egress identity for a VirtualNetwork. It is optional and handles outbound external access; ExternalIPAttachment handles inbound access. [Jira: OSAC-1433]
- **FR-11:** Providers configure networking implementations. Tenants do not select implementation backends, and adding a supported backend does not require a tenant API change. [Jira: OSAC-1433]
- **FR-12:** The supported deployment profile is connected networking with one provider-owned hub. ExternalIPPool accepts exactly one canonical IPv4 CIDR. IPv6, dual-stack, disconnected deployment, and multi-hub networking requests are rejected or reported unsupported. [Jira: OSAC-1433]
- **FR-13:** At tenant onboarding, the system creates a default VirtualNetwork,
  Subnet, NetworkACL, and NATGateway from provider-configured defaults. The
  tenant default ACL denies ingress by default and permits egress by default;
  because it is stateless, return traffic requires explicit reverse-direction
  ingress rules. The default Subnet is associated with the default NetworkACL,
  and tenant readiness waits until that association is ready. Workload creation
  can omit network attachment details to use these defaults. [User; OSAC-1433]
- **FR-14:** Existing workload traffic policies require tenant-assisted migration where their scope or stateful behavior cannot be represented by a Subnet-level stateless ACL. Tenants can group workloads by intended policy, place each group on a Subnet with the corresponding shared NetworkACL, and add reverse-direction rules where return traffic is required. [User]

### 3.2 Non-Functional Requirements

- **NFR-1:** Network isolation, ACL enforcement, address assignment, and external access behave consistently for VMaaS, CaaS, and BMaaS workloads. [Jira: OSAC-1433]
- **NFR-2:** Tenants receive validation errors before persistence or provisioning when a request violates the IPv4-only, same-VirtualNetwork association, single-attachment, or single-hub constraints. [OSAC-1433; User]

## 4. Acceptance Criteria

- [ ] Resources in different VirtualNetworks cannot communicate; Subnets in the same VirtualNetwork retain Layer 3 connectivity subject to their ingress and egress NetworkACL rules.
- [ ] A tenant can create a NetworkACL with ingress and egress rules that include ALLOW or DENY, order, protocol, optional TCP/UDP destination ports, and an IPv4 CIDR.
- [ ] Each direction has unique priorities from 1 through 32766; lower values are evaluated first, the first matching rule determines the result, and unmatched traffic is denied.
- [ ] Reply traffic is evaluated independently and passes only when the reverse direction has a matching rule.
- [ ] A Subnet can reference exactly one NetworkACL, and one NetworkACL can be associated with multiple Subnets in the same VirtualNetwork.
- [ ] NetworkACL rules and Subnet-to-NetworkACL associations are set at creation and cannot be updated; changes require deleting and recreating affected networking resources.
- [ ] All resources on one Subnet receive the same ACL policy; same-Subnet traffic is not filtered by that ACL.
- [ ] Cross-Subnet traffic must pass the source Subnet's egress rules and the destination Subnet's ingress rules.
- [ ] ComputeInstance, Cluster, and BaremetalInstance network attachments refer to a Subnet and contain no traffic-policy references; BMaaS can additionally select one interface.
- [ ] Workloads of all three service types can use the same networking resources, and each workload has at most one tenant network attachment.
- [ ] ExternalIPAttachment supports all three service types for inbound traffic, and NATGateway remains optional for outbound traffic.
- [ ] Default tenant readiness is not reported until the default NetworkACL is ready and associated with the default Subnet.
- [ ] Default-based workload creation stores and returns the resolved Subnet attachment.
- [ ] Unsupported IPv6, dual-stack, disconnected, and multi-hub configurations are rejected before provisioning.
- [ ] Existing policies that cannot be represented exactly are migrated through tenant-directed workload grouping and explicit reverse-direction ACL rules.
- [ ] Networking implementations remain hidden from tenant-facing APIs.

## 5. Dependencies

- **Unified Networking Design:** [/enhancements/OSAC-1433-unified-networking](/enhancements/OSAC-1433-unified-networking) defines the resource and API contract.
- **Default Networking:** [/enhancements/OSAC-1433-default-networking](/enhancements/OSAC-1433-default-networking) defines tenant defaults and simplified workload creation.
- **VMaaS, CaaS, and BMaaS networking enhancements:** define the service-specific attachment and provisioning behavior.
- Networking API, fulfillment, operator, fabric, and K8s networking components must implement the shared contract.

---

## Provenance

Authored: respond @ prd 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)
Phases: revise, respond

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"cc0daa6","source_repo":"06d340f90","source_repo_branch":"main","commits_behind_main":43,"commits_ahead_main":0,"main_ref":"main","phases":["revise","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
