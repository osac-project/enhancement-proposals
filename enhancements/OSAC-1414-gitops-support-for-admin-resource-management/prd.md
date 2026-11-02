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
- Git sync covers all current and future platform-scoped OSAC resource types,
  including CaaS, VMaaS, BMaaS, and networking resources. Future OSAC service
  APIs are included when they expose platform-scoped resource types. Platform-
  scoped means administered at the OSAC platform level rather than within an
  individual tenant's scope.
- OSAC polls registered Git references and applies their definitions through
  the OSAC API.
- OSAC applies the first revision it observes and retries failed resource
  operations on later syncs even if the Git reference has not advanced. Each
  retry reconciles the latest observed revision. [Clarify: R1.Q8]
- A slow or unavailable Git source does not delay unrelated API or CLI
  operations; Git resource changes are applied through the OSAC API.
- Admins can create or update resources not managed by Git through the API
  or CLI. The API provides create-or-update by resource name, and
  `osac apply -f` uses the same behavior. [Clarify: R1.Q6]
- Admins can see the latest observed commit SHA, whether that revision applied
  fully or partially, sync errors, and the resources managed by each Git
  reference.
- Manual updates and deletes of Git-managed resources are rejected through
  every API and CLI write path, including `osac apply -f`. Changes to these
  resources are applied through Git sync. [Clarify: R1.Q6]
- Deleting a Git reference retains its resources and removes that reference's
  Git management. Resources released from Git management can be edited or
  deleted through the API or CLI. [Clarify: R1.Q5]
- Git sync deletes resources only after a complete, unambiguous inventory shows
  they are absent from every active reference that can declare them. If
  overlapping declarations are supported, a resource remains while any active
  reference declares it. An apply error does not block unrelated deletions;
  dependent operations follow design-defined ordering and retry behavior,
  including deletions needed before replacements. [Clarify: R1.Q4, R1.Q9]
- Documentation explains how to register a Git source and check its sync
  results.

**Open question:** Can an admin detach an individual resource from Git
management while retaining its Git reference? **Owner:** Feature owner (to be
assigned). **Impact:** Determines whether individual resources can transition
to manual management without deleting the reference. [Clarify: R1.Q5]

**Open question:** Should Cloud Provider Admins have a UI to register and
configure Git references (repository, branch or tag, directory, existing
credential reference, and polling interval) and view the latest observed
commit SHA, sync errors, and resources associated with each reference, or are
API GitReference CRUD/status and `osac apply -f` sufficient? **Owner:** Feature
owner (to be assigned). **Impact:** Determines whether OSAC UI work for source
configuration and sync status is part of the feature. [Clarify: R1.Q7]

**Open question:** Does the feature support multiple concurrent Git references,
including references to different repositories? May the same platform resource
appear in more than one reference, or should overlapping declarations be
rejected? If overlap is supported, deletion waits until no active reference
declares the resource. **Owner:** Feature owner (to be assigned). **Impact:**
Determines reference cardinality and whether overlapping declarations are
accepted or rejected. [Clarify: R1.Q9]

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
- As a Cloud Provider Admin, I want deleting a Git reference to retain its
  resources and release them from that reference's management, so I can manage
  the released resources through the API or CLI. [Clarify: R1.Q5]
- As a Cloud Provider Admin, I want to choose how often each Git reference is
  checked so that changes are applied on a schedule I set. [Clarify: R1.Q3]
- As a Cloud Provider Admin, I want failed operations retried without a new Git
  commit and the latest revision's partial status reported so transient errors
  can recover. [Clarify: R1.Q8]
- As a Cloud Provider Admin, I want slow or unavailable Git sources not to
  delay unrelated API or CLI operations so that I can continue managing
  platform resources.
- As a Cloud Provider Admin, I want to create or update resources not managed
  by Git through the API or CLI (`osac apply -f`), so I can manage resources
  outside the Git workflow. [Clarify: R1.Q6]
- As a Cloud Provider Admin, I want to see the latest observed commit SHA,
  errors, managed resources, and whether that revision applied fully, so that I
  know whether the platform matches Git.
- As a Cloud Provider Admin, I want manual updates and deletes of Git-managed
  resources rejected through every API and CLI write path, including
  `osac apply -f`, so that Git remains the source of truth. [Clarify: R1.Q6]
- As a Cloud Provider Admin, I want resources removed from Git deleted only
  after complete inventories show they are absent from every active reference
  that can declare them, so a resource still desired by another reference is
  retained. [Clarify: R1.Q4, R1.Q9]

## Dependencies

- **Git repository access:** Admins need access to the registered repository
  and its selected branch or tag. Private repository credentials use existing
  secret references.

---

## Provenance

Authored: revise @ prd 0.11.5 - 7b2b8de, workspace main @ f0a8211
Phases: draft, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, respond, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"f0a8211","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
