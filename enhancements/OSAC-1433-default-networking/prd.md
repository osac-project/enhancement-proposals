---
title: default-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-10-22
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1433
see-also:
  - Unified Networking PRD: /enhancements/OSAC-1433-unified-networking/prd.md
  - Default Networking Design: /enhancements/OSAC-1433-default-networking/design.md
replaces:
  - N/A
superseded-by:
  - N/A
---

# Default Networking — Simplified Resource Creation

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1433 |
| Date        | 2026-10-22 |

The Unified Networking [deployment](/enhancements/OSAC-1433-unified-networking/prd.md#deployment-support-boundary) and [hub](/enhancements/OSAC-1433-unified-networking/prd.md#networking-hub-support-boundary) support boundaries apply.

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
    - [Default Networking](#default-networking)
    - [Optional Network Attachment with Defaults](#optional-network-attachment-with-defaults)
    - [Automatic External Access](#automatic-external-access)
    - [Default NATGateway](#default-natgateway)
- [5. Acceptance Criteria](#5-acceptance-criteria)
- [6. Dependencies](#6-dependencies)
- [7. Risks](#7-risks)
  - [7.1 ExternalIPPool exhaustion](#71-externalippool-exhaustion)
  - [7.2 Default SecurityGroup too permissive](#72-default-securitygroup-too-permissive)
  - [7.3 External access cleanup blocks deletion](#73-external-access-cleanup-blocks-deletion)
  - [7.4 Deployment misconfiguration](#74-deployment-misconfiguration)

## 1. Problem Statement

A reachable resource in OSAC needs 6+ sequential API calls: VirtualNetwork, Subnet, SecurityGroup, the resource itself, ExternalIP, and ExternalIPAttachment. Every tenant must learn the full networking model before its first VM, cluster, or bare-metal server. This slows onboarding, invites misconfiguration, and makes OSAC harder to adopt than platforms where one create command gives a reachable instance.

## 2. Goals and Non-Goals

### 2.1 Goals

Default networking supports IPv4 only.

- With provider networking enabled, a tenant creates an integrated workload with inbound and outbound connectivity in one API call, without pre-creating networking resources.
- Tenants who need custom networking keep the full explicit workflow; simplified creation is additive.
- Default and automatic networking resources are visible and follow the unified create/read/delete lifecycle; a change requires replacement, except the default SecurityGroup's rules, which a tenant can replace in place.

### 2.2 Non-Goals

- Custom defaults per tenant (all tenants of a deployment get the same default CIDRs and SecurityGroup rules).
- Auto-provisioning VirtualNetworks or Subnets beyond the defaults (tenants create more themselves).
- UI simplified creation beyond the workload wizards' "Use tenant default network" toggle ([UI design](/enhancements/OSAC-1433-unified-networking/ui-design.md#workload-network-attachment-pickers)); other simplified creation is API and CLI only.

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a resource (VM, cluster, or bare-metal server) without pre-creating networking resources, so that I start quickly with sensible defaults.
- As a Tenant User, I want to create a resource with `--external-ip-attachment` and have it externally reachable in one API call when provider networking is enabled.
- As a Tenant User, I want automatic ExternalIPs removed when I delete the workload, so that no orphaned resources accumulate.
- As a Tenant User, I want each externally reachable endpoint of a workload to get its own address and route once that endpoint is ready, without blocking provisioning.

### Tenant Admin Stories

- As a Tenant Admin, I want to inspect my default networking resources and create replacements when I need different settings.

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to configure a default CIDR range and default SecurityGroup rules on the NetworkClass, so that OSAC creates each tenant's default networking resources at onboarding.

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want to see whether a tenant's default networking resources were provisioned, so I can troubleshoot onboarding failures.

## 4. Requirements

### 4.1 Functional Requirements

#### Default Networking

- **FR-1:** Tenant onboarding provides default network resources, so tenants can create workloads without first building a network, and reports when the defaults are ready or what needs attention. With provider networking disabled, the default VirtualNetwork, Subnet, and SecurityGroup stay available for workload requests, but provider connectivity and outbound access are not promised.
- **FR-2:** The Cloud Infrastructure Admin sets the defaults (IPv4 CIDRs and SecurityGroup rules) on the NetworkClass through the installation's Helm values. Defaults are required: a NetworkClass without them is rejected, and so is one whose default Subnet range is too small for the deployment's address plan ([Unified PRD FR-1](/enhancements/OSAC-1433-unified-networking/prd.md#fr-1-network-isolation-and-connectivity-r1)). Enabling BMaaS or CaaS once tenant defaults exist is not supported ([Unified PRD Non-Goals](/enhancements/OSAC-1433-unified-networking/prd.md#23-non-goals)).
- **FR-3:** All tenants get the same default IPv4 CIDRs and stay isolated despite the overlap.
- **FR-4:** Default resources are labeled as defaults and visible in list and detail views. They follow the unified create/read/delete contract; a change means delete and recreate, except that a tenant can replace the default SecurityGroup's rules ([Unified PRD FR-8](/enhancements/OSAC-1433-unified-networking/prd.md#fr-8-createreaddelete-networking-contract-r8)). Tenants cannot delete them; they are removed with the Tenant.
- **FR-5:** Custom VirtualNetworks coexist with the defaults and do not affect them.

#### Optional Network Attachment with Defaults

- **FR-6:** A supported workload can be created without a network selection and use the tenant's defaults. For an incomplete selection, OSAC fills only the missing values and keeps the supplied ones; it applies the default SecurityGroup only when it belongs to the selected Subnet's VirtualNetwork, otherwise the caller must select compatible SecurityGroups. The resolved network is visible when the workload is retrieved.
- **FR-7:** A complete explicit attachment is kept as supplied, never replaced by a default.

#### Automatic External Access

Automatic external access is designed in [Unified — Automatic external access](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access).

- **FR-8:** With provider networking enabled, a Tenant User can request automatic inbound access when creating an integrating workload. OSAC accepts the request only when enough address capacity exists; otherwise the create fails and leaves no partial workload. With provider networking disabled, the request does not block provisioning, and that workload never gets external access. A workload service design may make automatic access mandatory (CaaS does for Clusters).
- **FR-9:** For a workload with several endpoints, OSAC gives each endpoint its own external address and route, available only once its address is assigned and the endpoint is ready. The workload service design names the endpoints.
- **FR-10:** Automatic inbound access never blocks a workload's bootstrap, unless a workload service design makes it mandatory and the workload bootstraps through it (CaaS workers reach the hosted API by its public name, through the API ExternalIP). A workload service design that makes it mandatory may report the workload ready only once that access is ready.
- **FR-11:** Tenants and administrators can identify automatically created addresses and routes. Workload deletion removes them; if provider cleanup fails, deletion stays pending with a diagnostic until cleanup succeeds; shared tenant defaults remain. With provider networking disabled, deletion stays available and needs no provider cleanup.

#### Default NATGateway

- **FR-12:** With provider networking enabled, the defaults give workloads in the tenant's default VirtualNetwork outbound connectivity. With it disabled, OSAC promises no outbound connectivity ([Unified PRD FR-10](/enhancements/OSAC-1433-unified-networking/prd.md#fr-10-provider-networking-control-at-installation)).

## 5. Acceptance Criteria

- [ ] With provider networking enabled, the tenant's default network and outbound access are ready before a workload relies on them.
- [ ] Default resources appear in list views with a label marking them as defaults.
- [ ] Tenants can read default resources but cannot delete them; the only in-place change is replacing the default SecurityGroup's rules; a Tenant Admin can create and select other resources.
- [ ] Tenants with identical default CIDRs stay isolated.
- [ ] A complete explicit network selection is kept; an omitted or incomplete one resolves to the tenant defaults where the shared rules permit, and the result is visible through the API.
- [ ] Each integrating workload service can request automatic inbound access without pre-creating an ExternalIP or ExternalIPAttachment (FR-8 to FR-11 verified per workload service design).
- [ ] With provider networking disabled, the default VirtualNetwork, IPv4 Subnet, and SecurityGroup stay available for defaulting, the default ExternalIP and NATGateway are absent, and no provider egress is promised.
- [ ] IPv6 and dual-stack default ranges are rejected.

## 6. Dependencies

- **Unified Networking:** the resource model of the [Unified Networking design](/enhancements/OSAC-1433-unified-networking/design.md).
- **ExternalIPPools:** provider networking exposes ready IPv4 capacity for default and automatic ExternalIPs.
- **Tenant onboarding:** creates the default resources.
- **Installation configuration:** valid NetworkClass defaults exist before tenant onboarding.

## 7. Risks

### 7.1 ExternalIPPool exhaustion

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** Pool capacity is visible in status; the error tells the tenant to contact the admin.

### 7.2 Default SecurityGroup too permissive

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** Minimal default rules on the NetworkClass; a Tenant Admin can tighten the default SecurityGroup's rules, also for running workloads, or create stricter SecurityGroups for later workloads.

### 7.3 External access cleanup blocks deletion

- **Owner:** Cloud Provider Admin
- **Mitigation:** With provider networking enabled, deletion stays pending while any automatic attachment or address remains; status names the failed cleanup task, and retries resume after provider repair.

### 7.4 Deployment misconfiguration

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** Defaults are required. The installer creates the NetworkClass from the Helm values, and a rollout whose values, address plan included, differ from the stored NetworkClass fails.

---

## Provenance

Authored: revise @ prd 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)
Final: manual-edit [manual] @ prd 0.11.5 - 0c7ea35, workspace main @ 14c4d6f1c (17 behind origin/main)

> Context changed between revise and manual-edit.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"0c7ea35","source_repo":"14c4d6f1c","source_repo_branch":"main","commits_behind_main":17,"commits_ahead_main":0,"main_ref":"main","phases":["revise","respond","revise","revise","revise","manual-edit","revise","manual-edit","revise","manual-edit","revise","respond","manual-edit"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
