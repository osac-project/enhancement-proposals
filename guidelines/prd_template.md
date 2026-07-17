---
title: feature-name
authors:
  - TBD
creation-date: yyyy-mm-dd
last-updated: yyyy-mm-dd
tracking-link:
  - TBD
---

To get started with this template:
1. **Create a directory.** Create a directory inside `enhancements/` using
   the naming convention `<area>-<description>-<ticket-id>`, all lowercase
   with hyphens (e.g., `enhancements/storage-backend-osac-1111/`). The
   ticket ID suffix is optional but recommended when a tracking issue exists.

   Common area prefixes:

   | Area | Scope |
   |------|-------|
   | `bmaas` | Bare metal provisioning and lifecycle |
   | `caas` | Kubernetes cluster provisioning (Hosted Control Planes) |
   | `vmaas` | KubeVirt-based virtual machine instances |
   | `networking` | VirtualNetwork, Subnet, SecurityGroup, DNS, PublicIP |
   | `storage` | StorageTier, StorageBackend, CSI, persistent volumes |
   | `compute` | ComputeInstance fields, instance types, snapshots |
   | `metering` | Usage tracking, billing, quota |
   | `infra` | Installation, Helm charts, platform prerequisites |
   | `core` | Tenant, secrets, RBAC, catalog, cross-cutting platform |
   | `ui` | Console features, wizards, dashboards |
2. **Make a copy of this template.** Copy this file into your directory
   as `prd.md`.
3. **Fill out the metadata** at the top (YAML front matter and the table
   below).
4. **Fill out each section.** If a section does not apply, mark it `N/A`
   rather than removing it.
5. **Create a pull request** against the main branch of this repository.
6. After the PRD is merged, create the design EP (`design.md`) in the
   same directory.

**Using the `/prd` skill (recommended):** If you are using an AI-assisted
development tool (Claude Code, Cursor, or similar), use the `/prd` workflow
instead of copying this template manually. Run `/prd:ingest` with your Jira
ticket to start the guided flow: ingest, clarify, draft, publish. The skill
produces a PRD that follows this template and publishes it as a PR.

For detailed authoring guidance, PRD vs design EP boundaries, personas,
and good/bad examples, see [prd_guide.md](prd_guide.md).

# {Title}

| Field       | Value   |
|-------------|---------|
| Author(s)   |         |
| Jira        |         |
| Date        |         |

## Problem Statement

Who is affected, what pain exists today, and what happens if this is not
addressed? Write from the user's perspective, not the system's.

## In Scope

What this PRD delivers. List user-facing capabilities and outcomes.

- {capability or outcome}

## Out of Scope

What is explicitly excluded to prevent scope creep. Include items that
readers might reasonably expect but are deferred or intentionally omitted.

- {excluded item and brief reason}

## User Stories

Group stories by persona. Use the standard formula:
"As a {persona}, I want {capability} so that {outcome}."

Ground each story in concrete artifacts, workflows, or scenarios. Name
the specific things users interact with. See [prd_guide.md](prd_guide.md)
for OSAC personas and good/bad examples.

### {Persona name}

- As a {persona}, I want {capability} so that {outcome}.

## Assumptions

<!-- Optional: omit this section if no unverified assumptions underpin
the requirements. -->

Statements believed to be true but not yet verified. If an assumption
turns out to be wrong, it may change the scope or approach.

- {assumption}

## Dependencies

<!-- Optional: omit if no external dependencies exist. -->

External teams, services, or milestones that this work depends on.

- **{Dependency name}:** {What it provides and any ordering constraints}
