# PRD Author Guide

This guide explains how to write a Product Requirements Document (PRD) for
OSAC. It covers what a PRD is, how it differs from a design enhancement
proposal (EP), the personas to write for, and common mistakes to avoid.

## What is a PRD?

A PRD describes **what** the product must do and **why**, from the user's
perspective. It defines user-facing capabilities, outcomes, and success
criteria. It does not describe how the system implements those capabilities.

A PRD answers:
- Who is affected?
- What pain exists today?
- What can users do after this ships?
- How will we know it works?

## PRD vs Design EP

OSAC uses a two-stage enhancement process. The PRD comes first and defines
the requirements. The design EP follows and specifies the implementation.

| | **PRD** (`prd.md`) | **Design EP** (`design.md`) |
|---|---|---|
| **Audience** | Product managers, reviewers, stakeholders | Engineers, architects |
| **Focus** | User-facing capabilities and outcomes | Architecture, API fields, reconciliation logic |
| **Content** | User stories, in/out of scope, success criteria | CRD schemas, controller design, playbook parameters |
| **Lifecycle** | Merged before design work begins | Merged before implementation begins |

**Litmus test:** Could a product manager verify this by using the product?
If yes, it belongs in the PRD. If it requires reading source code, it
belongs in the design EP.

### What belongs where

| PRD (user-observable) | Design EP (implementation) |
|---|---|
| "Tenants can create persistent volumes on CaaS clusters" | CRD fields, conditions, finalizers |
| "Storage readiness is visible on the cluster status" | Controller reconcile logic |
| "Clusters are reachable without manual networking setup" | Playbook names, API schemas |
| "Admins can see storage readiness across all tenants" | Helm/installer changes |

### Platform vocabulary is not design leakage

Referencing OSAC platform terms by name is acceptable context in a PRD:

- **Platform:** OpenShift, Kubernetes, Hosted Control Planes
- **Services:** BMaaS, CaaS, VMaaS, MaaS, Enclave
- **User-facing resources:** ClusterOrder, ComputeInstance, Tenant,
  VirtualNetwork, Subnet, SecurityGroup, PublicIPPool, PublicIP,
  StorageClass
- **Tools:** kubectl, grpcurl, Helm

Naming these is fine. Mandating which internal component solves a problem
or describing controller logic is not.

## OSAC Personas

Use these exact names in user stories. Every PRD should identify which
personas are affected.

| Persona | Role | Examples |
|---------|------|----------|
| **Cloud Provider Admin** | Works for the cloud provider. Handles tenant onboarding, sets quotas, manages global catalogs. Super-user who can see all tenants. | Tenant onboarding, quota management, global template catalogs |
| **Cloud Infrastructure Admin** | Works for the cloud provider. Manages core infrastructure: network, firewall, compute, storage. Integrates control plane with local infrastructure. | Network classes, IP pools, storage tiers, DNS, Netris/VAST/ESI integration |
| **Tenant Admin** | Works for the tenant organization. Manages their org's config, users, IDP, quotas, and org-specific catalogs. Can only see their own organization. | Create networking objects, manage tenant resources, onboard users |
| **Tenant User** | Works for the tenant organization. Self-service provisions cloud resources, manages full lifecycle. Prefers click-ops but wants API/CLI for automation. | Order machines/clusters/VMs, manage instance lifecycle, view quota |

## Writing Good User Stories

Use the standard formula:

> As a **{persona}**, I want **{capability}** so that **{outcome}**.

Ground each story in concrete artifacts, workflows, or scenarios. Name the
specific things users interact with.

### Good examples

- "As a Tenant User, I want to retrieve cluster kubeconfig and admin
  password via the secrets API, so that I can access my provisioned
  cluster without asking an administrator."
- "As a Cloud Infrastructure Admin, I want to configure a storage backend
  once per deployment, so that tenants get persistent storage on new
  clusters automatically."
- "As a Tenant Admin, I want to store OIDC client secrets for IDP
  integration, so that my team's identity provider credentials are
  centrally managed."

### Bad examples

- "As a user, I want to create and manage secrets." (Too vague. Which
  secrets? SSH keypairs? OIDC credentials? Kubeconfigs? "User" is not an
  OSAC persona.)
- "As a Tenant User, I want the controller to reconcile storage within
  30 seconds." (Design leakage. Users do not observe controllers.)
- "As an admin, I want storage support." (Vague persona, vague
  capability. Which admin? What does "support" mean?)

### Tips

- One capability per story. If a story has "and", split it.
- Name the artifacts: "SSH keypairs and OIDC client secrets" not "secrets."
- State the outcome in terms of what the user can then do, not what the
  system does internally.

## Common Mistakes

### Design leakage

The most common PRD failure mode. Symptoms:

- Naming controllers, reconcilers, or finalizers
- Describing playbook parameters or AAP job templates
- Specifying internal API conditions or environment variables
- Mandating which component solves the problem

**Fix:** Describe the user-observable outcome. "Storage is automatically
available on new clusters" instead of "The storage controller invokes
osac-create-tenant-cluster-storage with provisioning_target=hcp_data_plane."

### Vague requirements

- "Storage should be available" (which clusters? what does "available"
  mean to the user?)
- "Networking should work" (which networking objects? for which services?)

**Fix:** Be specific about what users can do and see. "Tenants can create
persistent volumes using StorageClasses on their CaaS cluster within
5 minutes of the cluster becoming ready."

### Missing personas

A PRD that names no personas has an unclear audience. Every user story
must use an OSAC persona name from the table above.

### Bundling unrelated capabilities

A PRD that covers storage provisioning, networking policy enforcement,
and cluster monitoring is three features, not one. Test independence:
could each ship on its own and provide value? If yes, split them.

## Workflow

### Using the `/prd` skill (recommended)

If you are using an AI-assisted development tool (Claude Code, Cursor, or
similar), the `/prd` workflow automates PRD creation:

1. **`/prd:ingest`** with your Jira ticket to gather requirements
2. **`/prd:clarify`** to resolve ambiguities through Q&A
3. **`/prd:draft`** to generate the PRD from the template
4. **`/prd:publish`** to create a PR on enhancement-proposals

The skill produces a PRD that follows the
[prd_template.md](prd_template.md) and can be reviewed with `/prd-review`.

### Manual workflow

1. Create a directory: `mkdir enhancements/<area>-<description>/`
2. Copy the template: `cp guidelines/prd_template.md enhancements/<area>-<description>/prd.md`
3. Fill out all sections
4. Self-review using `/prd-review` if available, or check against the
   common mistakes above
5. Create a pull request against `main`
6. After the PRD is merged, create the design EP (`design.md`) in the
   same directory using `guidelines/enhancement_template.md`

## Review

PRDs are reviewed against five criteria: clear user-facing need, business
justification, freedom from design leakage, focused scope, and testable
requirements. Use `/prd-review` for a detailed automated assessment before
submitting your PR.

## External References

- [Perforce: How to Write a PRD](https://www.perforce.com/blog/alm/how-write-product-requirements-document-prd)
- [Atlassian: Agile Product Requirements](https://www.atlassian.com/agile/product-management/requirements)
