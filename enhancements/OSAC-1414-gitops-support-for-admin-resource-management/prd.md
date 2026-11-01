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
- OSAC polls registered Git references and applies definitions through the
  OSAC API for all current and future platform-scoped OSAC resource types.
  Platform-scoped means administered at the OSAC platform level rather than
  within an individual tenant's scope.
- OSAC applies the first revision it observes and retries failed resource
  operations on later syncs even if the Git reference has not advanced. Each
  retry reconciles the latest observed revision. [Clarify: R1.Q8]
- Git synchronization is independently operated from normal OSAC API request
  handling. A slow or unavailable Git source does not block unrelated API or
  CLI operations; resource changes go through the OSAC API.
- The API and CLI can create or update resources not managed by Git. The CLI
  command is `osac apply -f`. [Clarify: R1.Q6]
- Admins can see the last applied commit, whether the latest revision applied
  fully or partially, sync errors, and the resources managed by each Git
  reference.
- Direct API updates and deletes for Git-managed resources are rejected.
  [Clarify: R1.Q6]
- Resources are deleted only when complete, unambiguous inventories across all
  active Git references show that no reference declares them. An apply error
  does not block unrelated deletions; dependent operations follow design-defined
  ordering and retry behavior, including deletions needed before replacements.
  [Clarify: R1.Q4]
- Documentation explains how to register a Git source and check its sync
  results.

**Open question:** Is disabling a Git reference supported? When an admin
deletes or disables one, are its managed resources deleted, retained under Git
management, or released for manual changes? Can an admin detach a resource for
manual management? **Owner:** Feature owner (to be assigned). **Impact:**
Resource retention and the move to manual management remain unclear.
[Clarify: R1.Q5]

**Open question:** May admins directly create or update platform-scoped
resources not managed by Git, or may only the Git sync runtime write any
in-scope platform resource? **Owner:** Feature owner (to be assigned).
**Impact:** Determines whether write authorization is uniform across in-scope
resource types or requires tracking Git ownership per resource. [Clarify: R1.Q6]

**Open question:** Should Cloud Provider Admins have a UI to register and
configure Git references (repository, branch or tag, directory, existing
credential reference, and polling interval) and view the last applied commit,
sync errors, and resources associated with each reference, or are API
GitReference CRUD/status and `osac apply -f` sufficient? **Owner:** Feature
owner (to be assigned). **Impact:** Determines whether OSAC UI work for source
configuration and sync status is part of the feature. UI deletion/disable
behavior depends on R1.Q5. [Clarify: R1.Q7]

## Out of Scope

- Webhook triggers. The system uses polling.
- Replacing Argo CD or Flux for Kubernetes resource management; those tools
  remain complementary.
- Tenant-facing resource GitOps.
- All-or-nothing apply across multiple files.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to register a repository, branch or tag,
  and directory so that the platform can apply the resource files in it.
- As a Cloud Provider Admin, I want to choose how often each Git reference is
  checked so that changes are applied on a schedule I set. [Clarify: R1.Q3]
- As a Cloud Provider Admin, I want failed operations retried without a new Git
  commit and the latest revision's partial status reported so transient errors
  can recover. [Clarify: R1.Q8]
- As a Cloud Provider Admin, I want slow or unavailable Git sources not to
  block unrelated API or CLI operations so that I can continue managing
  platform resources.
- As a Cloud Provider Admin, I want to see the last applied commit, errors, and
  managed resources, and whether the latest revision applied fully, so that I
  know whether the platform matches Git.
- As a Cloud Provider Admin, I want direct API updates and deletes of
  Git-managed resources rejected so that Git remains the source of truth.
  [Clarify: R1.Q6]
- As a Cloud Provider Admin, I want resources removed from Git deleted only
  after complete, unambiguous inventories across active Git references show
  that none declares them, so the platform follows the repository safely.
  [Clarify: R1.Q4]
- As a Cloud Provider Admin, I want to use the API or `osac apply -f` to create
  or update resources not managed by Git. [Clarify: R1.Q6]

## Dependencies

- **Git repository access:** Admins need access to the registered repository
  and its selected branch or tag. Private repository credentials use existing
  secret references.

---

## Provenance

Authored: respond @ prd 0.11.5 - 7b2b8de, workspace main @ f0a8211
Phases: draft, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"f0a8211","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
