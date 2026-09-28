# OSAC MCP Server for infrastructure provisioning

| Field | Value |
|---|---|
| Author(s) | Tommy Hughes |
| Jira | [OSAC-5731](https://redhat.atlassian.net/browse/OSAC-5731) |
| Date | 2026-09-28 |

## Problem Statement

OSAC users can manage infrastructure through existing OSAC interfaces, and the [ComputeInstance MCP PoC](https://redhat.atlassian.net/browse/OSAC-4388) demonstrates one catalog-backed VM request, but that PoC is not a supported product experience. Tenant users cannot yet rely on a documented model-host connection to discover eligible infrastructure, handle authorized prerequisites, review writes, and check actual outcomes across the selected resource journeys. Administrators also need a way to attribute and diagnose model-initiated requests within their permitted scope. Without this feature, model-assisted deployment remains demo-specific, and an accepted request can be mistaken for a ready resource.

## In Scope

- Target OSAC 0.6 with staged, end-to-end MCP journeys: tenant networking first, plus VMaaS ComputeInstances, CaaS clusters, BMaaS bare-metal instances, and a later OSAC Volume stage. A stage is complete only when an authorized user can discover eligible choices, handle supported prerequisites, perform applicable existing lifecycle actions, and retrieve the actual outcome in a later session. [Clarify: R2.Q1, R4.Q1, R11.Q3]
- The networking journey covers VirtualNetworks, Subnets, SecurityGroups, external IP allocation and attachment, and NAT egress where OSAC supports them. When an existing network resource cannot be edited in place, the user is told so and may review a supported replacement path; nothing is silently replaced or deleted. [Clarify: R9.Q1, R14.Q1]
- Catalog offerings and templates, host and instance types, cluster versions, disk images, storage tiers, Projects, and selected prerequisites are discoverable or manageable only to the extent that OSAC already supports the action and authorizes the caller. Authorized admins can manage provider-owned or tenant-scoped offerings and Projects within their existing permissions. [Clarify: R2.Q2, R3.Q1, R3.Q2, R10.Q1]
- An authorized user can provide a missing deployment Secret through an OSAC-controlled interaction outside the model host, then continue using its reference. Model-facing actions do not accept or reveal plaintext Secret values. [Clarify: R10.Q2]
- Supported connections are the locally running Cursor editor and CLI, Codex CLI and app/IDE, and Claude Code CLI and Desktop Code experience, against an OSAC endpoint reachable from the user's environment. The OSAC UI provides a discoverable entry point and copyable endpoint, trust, sign-in, and read-only verification guidance. Each supported host surface is verified with a deployment journey. [Clarify: R4.Q2, R13.Q1, R13.Q2, R13.Q3]
- Discovery and writes are authorized as the signed-in caller, retaining OSAC tenancy, catalog limits, and validation. Users review a multi-step plan and may deny each write; higher-impact writes have separate confirmation. Authorized admins can inspect who initiated an MCP write, its MCP origin, tenant, action, resource, and outcome, and authorized operators can follow it to the related provisioning work. [Clarify: R5.Q1, R5.Q3, R8.Q1, R8.Q2, R14.Q4]
- The supported MCP actions, deployment, onboarding, and diagnostics are documented. Resource journeys are validated through appropriate automated and end-to-end tests, including failure and later-session status paths. [Clarify: R11.Q3, R13.Q3, R14.Q3]

## Out of Scope

- An Observability MCP, event streaming, interactive serial or VNC console access, SSH or other in-guest access, and application deployment or configuration inside provisioned infrastructure. Resource status and conditions remain part of the deployment journey. [Clarify: R12.Q1]
- An unrestricted proxy into Fulfillment or Kubernetes, new underlying OSAC infrastructure-management actions, and dedicated user, identity-provider, role, role-binding, or project-membership administration. [Clarify: R2.Q2, R11.Q1]
- A separately verified model or agent identity beyond the authenticated caller and MCP-origin indication. [Clarify: R8.Q2]
- Cloud-run agents and Claude Desktop's separate Chat connector for a private OSAC endpoint, a one-click host installer, MCP/OSAC-CLI action parity, and CLI-driven model-host configuration. [Clarify: R13.Q1, R13.Q2, R13.Q4]
- A separate dry-run operation, a required plan-wide “approve all” choice, and a separate Kubernetes PVC-management journey. [Clarify: R7.Q1, R7.Q3, R9.Q2]
- A complete FabricDomain journey without verified underlying OSAC provisioning and role support. [Clarify: R10.Q3]

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want MCP requests to honor the catalog and tenant controls I configure, so that a model host cannot bypass OSAC governance.
- As a Cloud Provider Admin, I want to create, update, and publish provider-owned VM, cluster, and bare-metal catalog offerings through MCP within my existing permissions, so that users can request governed infrastructure without an administrative shortcut. [Clarify: R3.Q2]
- As a Cloud Provider Admin, I want to confirm each provider-offering publication before it changes what tenants may request, so that catalog exposure is intentional. [Clarify: R5.Q3]
- As a Cloud Provider Admin, I want to inspect MCP write records showing the caller, tenant, action, resource, and outcome within my authorized visibility, so that I can audit model-initiated changes. [Clarify: R8.Q1, R8.Q2]

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want a supported OSAC installation path for the MCP service, so that I can make it available to tenant users.
- As a Cloud Infrastructure Admin, I want documented health and connection checks that distinguish certificate-trust failures, sign-in failures, permission denials, and service failures, so that I can direct users to the relevant remedy. [Clarify: R13.Q3]
- As a Cloud Infrastructure Admin, I want to trace an authorized MCP write to its Fulfillment resource and provisioning work, so that I can investigate its outcome without a separate Observability MCP. [Clarify: R14.Q4]

### Tenant Admin

- As a Tenant Admin, I want my organization's catalog visibility and member permissions to apply to MCP requests, so that members see and request only what their OSAC roles allow.
- As a Tenant Admin, I want to create and update Projects through MCP when my role permits it, so that a deployment can use the intended Project. [Clarify: R10.Q1]
- As a Tenant Admin, I want to create or update tenant-scoped catalog offerings when my existing role permits it, so that tenant members can request eligible resources without a privileged MCP identity. [Clarify: R3.Q1, R3.Q2]
- As a Tenant Admin, I want to inspect MCP write records for my permitted tenant scope, so that I can identify the caller, change, and outcome without seeing another tenant's activity. [Clarify: R8.Q1]

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to find OSAC's host-specific MCP setup instructions in the UI and complete sign-in and certificate trust for a supported local host, so that I can connect without a demo-only runbook. [Clarify: R13.Q1, R13.Q2]
- As a Tenant Admin or Tenant User, I want to verify my connection with a read-only request before provisioning, so that I know whether discovery works without changing infrastructure. [Clarify: R13.Q3]
- As a Tenant Admin or Tenant User, I want to discover eligible catalog offerings and their selectable images, sizes, storage, networking, and other prerequisites, so that I can choose only resources my role may use. [Clarify: R1.Q2, R11.Q3]
- As a Tenant Admin or Tenant User, I want to create missing VirtualNetworks, Subnets, SecurityGroups, and supported public-address or egress resources when authorized, so that I can satisfy a deployment's networking prerequisites. [Clarify: R1.Q3, R9.Q1]
- As a Tenant Admin or Tenant User, I want to request a ComputeInstance from a published catalog offering with permitted VM size, image, boot storage, and network choices, so that the requested VM matches my needs and catalog limits. [Clarify: R2.Q1, R11.Q3]
- As a Tenant Admin or Tenant User, I want to request an eligible cluster through MCP, so that I can complete the CaaS provisioning journey using my existing permissions. [Clarify: R2.Q1, R3.Q1]
- As a Tenant Admin or Tenant User, I want to request an eligible bare-metal instance through MCP, so that I can complete the BMaaS provisioning journey using my existing permissions. [Clarify: R2.Q1, R3.Q1]
- As a Tenant Admin or Tenant User, I want to request and manage an OSAC Volume through MCP where my role permits it, so that I can use the supported storage lifecycle without treating a Kubernetes PVC as an MCP resource. [Clarify: R4.Q1, R9.Q2]
- As a Tenant Admin or Tenant User, I want to update or delete my eligible infrastructure when OSAC supports that action, so that I can manage its lifecycle without a model inventing unsupported operations. [Clarify: R1.Q2, R2.Q2]
- As a Tenant Admin or Tenant User, I want to start, stop, or restart an eligible ComputeInstance through explicit actions, so that I can control its VM lifecycle and check the actual result. [Clarify: R14.Q2]
- As a Tenant Admin or Tenant User, I want to review the full sequence of a multi-resource request before execution, so that I understand its dependencies and proposed changes. [Clarify: R5.Q1]
- As a Tenant Admin or Tenant User, I want to approve or deny each write before execution, so that I control which resources change. If an action, target, or setting changes, I see the revised proposal before that write proceeds. [Clarify: R5.Q1, R6.Q2, R7.Q1]
- As a Tenant Admin or Tenant User, I want any deletion, public exposure, or offering publication my role permits to require separate confirmation of its specific effect, so that a general plan review cannot authorize a higher-impact change. [Clarify: R5.Q3]
- As a Tenant Admin or Tenant User, I want a missing prerequisite I cannot create to be identified and the request stopped, so that I know what requires an authorized administrator rather than an identity escalation. [Clarify: R2.Q4]
- As a Tenant Admin or Tenant User, I want to supply missing deployment Secret values through an OSAC-controlled interaction outside the model host and resume using only the reference, so that sensitive values do not enter the model conversation. [Clarify: R10.Q2]
- As a Tenant Admin or Tenant User, I want to be told when an existing network resource cannot be edited in place and shown a separately reviewable replacement proposal where supported, so that I can decide what happens to the old resource. [Clarify: R14.Q1]
- As a Tenant Admin or Tenant User, I want to return in a later session and see a resource's ID, actual state, available reasons and timing, and remaining unknowns, so that I can distinguish request acceptance from readiness or failure. [Clarify: R8.Q3, R14.Q3]
- As a Tenant Admin or Tenant User, I want a multi-resource request to stop after a failed step without making further changes and show which steps succeeded, which failed, and which resources remain, so that I can decide what to do next without an automatic rollback. [Clarify: R5.Q2]
- As a Tenant Admin or Tenant User, I want an uncertain create result checked and reported as unknown if it cannot be established, so that an automatic retry does not create duplicate infrastructure. [Clarify: R7.Q2]

## Dependencies

- **Existing OSAC capabilities:** Each selected journey depends on OSAC already offering the relevant actions to authorized users and on the corresponding infrastructure capability being available. A stage is complete only when users can satisfy its prerequisites and verify actual outcomes, not merely discover an operation. [Clarify: R2.Q2, R11.Q3]
- **Volume integration:** The OSAC Volume journey depends on a working volume lifecycle and a clear user path for using Volumes alongside existing storage workflows. [Clarify: R4.Q1, R9.Q2]
- **Identity and private connectivity:** Supported hosts depend on a reachable OSAC endpoint, certificate trust, and the existing OSAC/Keycloak sign-in and permissions path. Host-specific instructions may point to the host's official documentation where that behavior is maintained. [Clarify: R3.Q1, R13.Q1, R13.Q3]

---

## Provenance

Authored: respond @ prd 0.11.3 - 2bd6607, workspace OSAC-4388-deployment-mcp-poc @ 199459d7b (dirty)
Phases: draft, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"199459d7b (dirty)","source_repo_branch":"OSAC-4388-deployment-mcp-poc","commits_behind_main":0,"commits_ahead_main":1228,"main_ref":"main","phases":["draft","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
