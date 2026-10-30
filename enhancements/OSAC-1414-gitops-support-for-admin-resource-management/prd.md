# GitOps support for admin resource management

| Field | Value |
|-------|-------|
| Author(s) | Haim Tayrie |
| Jira | [OSAC-1414](https://redhat.atlassian.net/browse/OSAC-1414) |
| Date | 2026-10-28 |

## Problem Statement

Cloud Provider Admins manage platform resources through direct API calls or
CLI commands. These methods are error-prone and make it hard to review changes
or keep one source of truth. Without a managed Git workflow, admins cannot
reliably prevent or spot drift. A Git-based workflow lets admins review changes
before they reach the platform and check whether they were applied.

## In Scope

- Admins can create, view, update, and delete Git references through the API.
  Each reference identifies a repository, branch or tag, directory, credential
  reference, and configurable polling interval. [Clarify: R1.Q3]
- OSAC polls registered Git references and applies the listed resource
  definitions through the OSAC API when it detects a new commit. It applies
  files for `ClusterTemplate`,
  `ComputeInstanceTemplate`, `ClusterCatalogItem`,
  `ComputeInstanceCatalogItem`, `NetworkClass`, shared `DiskImage`,
  `BareMetalInstanceTemplate`, `BareMetalInstanceCatalogItem`, `PublicIPPool`,
  and `Hub`.
- The API and CLI can create or update a resource from a definition. The CLI
  command is `osac apply -f`.
- Admins can see the last applied commit, sync errors, and the resources
  managed by each Git reference.
- Direct API updates and deletes for Git-managed resources are rejected.
- Resources removed from Git are deleted after a complete sync with no apply
  errors. If any apply fails, deletion waits for a later error-free sync.
  [Clarify: R1.Q4]
- Documentation explains how to register a Git source and check its sync
  results.

**Open question:** What happens to managed resources if an admin deletes or
disables a Git reference? To be determined whether those resources are deleted,
kept under Git management, or released for manual changes. **Owner:** To be
determined. **Impact:** Resource retention and the move to manual management
remain unclear. [Clarify: R1.Q5]

## Out of Scope

- Webhook triggers. The system uses polling.
- Replacing Argo CD or Flux for Kubernetes resource management; those tools
  remain complementary.
- Tenant-facing resource GitOps and new secret management. Existing secret
  references are used.
- All-or-nothing apply across multiple files.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to register a repository, branch or tag,
  and directory so that the platform can apply the resource files in it.
- As a Cloud Provider Admin, I want to choose how often each Git reference is
  checked so that changes are applied on a schedule I set. [Clarify: R1.Q3]
- As a Cloud Provider Admin, I want to see the last applied commit, errors, and
  managed resources so that I know whether the platform matches Git.
- As a Cloud Provider Admin, I want direct API updates and deletes of
  Git-managed resources rejected so that Git remains the source of truth.
- As a Cloud Provider Admin, I want resources removed from Git deleted after a
  clean sync so that the platform follows the repository. [Clarify: R1.Q4]
- As a Cloud Provider Admin, I want to apply a resource definition through the
  API or `osac apply -f` so that I can create or update resources directly.

## Dependencies

- **Git repository access:** Admins need access to the registered repository
  and its selected branch or tag. Private repository credentials use existing
  secret references.

---

## Provenance

Authored: respond @ prd 0.11.5 - 7b2b8de, workspace main @ f0a8211
Phases: draft, respond, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"f0a8211","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
